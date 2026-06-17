# GLM-OCR Self-Hosted LAN Service — Design

**Date:** 2026-06-17
**Status:** Approved (design phase, refined via grill-with-docs)
**Author:** brainstorming session

## Goal

Self-host a GLM-OCR document-recognition service on this PC so other computers on
the same LAN can submit PDFs and images over HTTP and receive extracted content as
Markdown (with LaTeX for formulas). The service must be reliable, fast, good
quality, and persistent across reboots.

## Target Machine (inspected 2026-06-17)

| Component | Value |
|-----------|-------|
| OS | Ubuntu 26.04 LTS on **WSL2** (Windows host), kernel 6.18 |
| CPU | Intel Core Ultra 9 285, 24 cores |
| RAM | 31 GiB + 8 GiB swap |
| Disk | 943 GB free on `/` |
| GPU | NVIDIA RTX 4000 SFF Ada, **20 GB VRAM** (driver 596.59, CUDA 13.2 capable) |
| System Python | 3.14.4 (too new for vLLM wheels — avoided by containerizing) |
| Docker | not installed (to be installed) |
| Network egress | Direct HTTPS (port 443) works. `http_proxy` set to `proxy.example.com:8080` for plain HTTP only; `https_proxy` unset. HF, vLLM wheels, Docker Hub, GitHub all reachable. |

**Substrate decision:** Stay on WSL2 + Docker. Native Windows cannot host vLLM
(Linux-only; on Windows it runs via WSL2/Docker anyway). Docker Desktop on Windows
uses the WSL2 backend regardless. GPU passthrough into WSL2 is confirmed working.

## Model Choice

**`zai-org/GLM-OCR`** — 0.9B parameters, MIT license, released 2026-01-27.

Rationale:
- Purpose-built document OCR. Tops OmniDocBench V1.5 with 94.62, beating general
  VLMs up to 235B parameters.
- 0.9B → roughly 2 GB VRAM in BF16. Fits the 20 GB GPU with large headroom. Full
  BF16 quality costs nothing here, so no quantization needed.
- ~1.86 pages/second PDF throughput.
- Native vLLM OpenAI-compatible serving. Outputs Markdown with LaTeX formula and
  table recognition.

Tradeoffs:
- vs larger (e.g. GLM-4.5V 9B): general VLM, ~18 GB BF16, slower, weaker on pure
  document OCR, no reasoning benefit for OCR. Rejected.
- vs smaller / llama.cpp INT4 quants: unnecessary — a dedicated GPU is present, so
  full-precision BF16 is the higher-quality, no-cost choice. Rejected.

### Backend version facts (confirmed)
- vLLM **nightly** build required (model too new for a stable release).
- `transformers >= 5.0.0`, installed from source.
- MTP speculative decoding: `--speculative-config.method mtp
  --speculative-config.num_speculative_tokens 1`.
- glmocr `[selfhosted]` extra pulls **PaddlePaddle** for PP-DocLayout-V3 layout.
- glmocr's own Flask server (`:5002 /glmocr/parse`) accepts only JSON lists of
  **server-local image paths** — not multipart uploads, not PDFs. Therefore it is
  NOT used as the LAN front door; we drive the glmocr **Python API** from our own
  gateway instead.

## Architecture

**Two containers** in one Docker Compose stack (Caddy dropped — the gateway
enforces auth itself):

1. **vllm** — serves `zai-org/GLM-OCR` (BF16), OpenAI-compatible API on internal
   port 8080, GPU via nvidia-container-toolkit. Flags: `--max-model-len 8192`,
   MTP speculative decoding, `--allowed-local-media-path`. Not exposed to LAN.
   Gets the full GPU (Paddle runs on CPU, see below).
2. **gateway** — FastAPI app (the LAN front door, the only published port,
   `0.0.0.0:8080` on the host). Uses the **glmocr Python API** as a library:
   accepts a multipart-uploaded PDF or image, rasterizes PDFs via the SDK's
   `PageLoader`, runs PP-DocLayout-V3 layout (**CPU**), calls the vllm service for
   region OCR, assembles Markdown/LaTeX, and returns JSON. Enforces the API key.

### Data flow

```
LAN client ──POST /ocr (multipart file + X-API-Key)──> gateway:8080 (host)
                                                          │
                            (validate key, page cap, rasterize PDF, layout on CPU)
                                                          │ OpenAI API
                                                          ▼
                                                    vllm:8080 (GLM-OCR on GPU)
                                                          │
                              JSON {markdown, pages, elapsed_sec, filename} ◀──
```

## API Contract

- `POST /ocr` — multipart upload, field `file` (PDF or image). Header
  `X-API-Key` required. Returns `200`:
  ```json
  {"markdown": "...", "pages": 12, "elapsed_sec": 6.4, "filename": "x.pdf"}
  ```
  Markdown carries inline/blocks LaTeX (`$...$` / `$$...$$`) and tables.
- `GET /health` — readiness (gateway up + vllm reachable). No auth.
- Errors: `401` (missing/bad key), `413` (over `MAX_PAGES`), `415` (unsupported
  type), `503` (busy queue full / vllm not ready).

## Behavior Decisions (from grill-with-docs)

- **Processing mode:** synchronous. `POST /ocr` blocks until done, returns Markdown.
  No async job queue (YAGNI for interactive LAN use).
- **Page cap:** `MAX_PAGES` default **50**; larger documents rejected with `413`.
- **Concurrency:** **1** in-flight OCR job (`MAX_CONCURRENCY=1`), others wait on a
  bounded queue; `503` when the queue is full. Predictable latency/memory.
- **Interface:** REST only. No web UI (clean header-key auth for machine clients).
- **Layout engine:** PP-DocLayout-V3 on **CPU** (24 cores idle; avoids a second
  CUDA stack in the gateway image and any VRAM contention). vLLM keeps the full GPU.
- **Response shape:** JSON envelope (see API Contract).

## Persistence

- Named Docker volumes: HuggingFace cache (GLM-OCR weights) and Paddle cache
  (layout weights). Downloaded once, survive container recreation.
- All services `restart: unless-stopped`.
- Docker (with the stack) starts when WSL/Docker starts → service returns after
  reboot without manual steps.

## Model / Weights Acquisition

- Auto-download on first start into the named volumes (GLM-OCR ~2 GB via vLLM;
  PP-DocLayout-V3 weights via gateway). Both public; no HF token needed.
- **Pin the working vLLM nightly by digest** once verified during implementation
  (not a floating `latest`) → reproducible, won't silently break on reboot.
- HTTPS egress is direct and confirmed; no proxy needed for downloads. Still
  propagate the host `http_proxy` into containers and set `NO_PROXY` for internal
  traffic (`localhost,127.0.0.1`, service name `vllm`, the LAN subnet) so
  gateway↔vllm and LAN responses never route through the proxy.

## Security

- Single shared API key, auto-generated into `.env` (git-ignored) at setup, sent
  as `X-API-Key`. Gateway rejects requests without a valid key (`401`).
- Only the gateway port (`8080`) is published; vllm stays on the internal Compose
  network.
- Documented firewall guidance to scope the published port to the LAN subnet.
- Plain HTTP, justified by a trusted LAN. Documented upgrade path to self-signed
  HTTPS (add a TLS reverse proxy) if the network becomes untrusted.

## Output Handling

- Markdown is the primary output; embedded math as LaTeX, tables as Markdown/HTML
  per the SDK. Multi-page PDFs assembled into one Markdown document (SDK treats an
  image list as pages of one document).

## Testing Strategy

- **Unit:** PDF→image rasterization sanity; API-key rejection (`401` without key);
  page-cap rejection (`413` over 50 pages).
- **Integration:** feed a sample PDF and a sample image, assert non-empty Markdown
  and that a known formula/table is present.
- **LAN smoke:** from a second PC, run the client against `<host-ip>:8080` with the
  key; confirm Markdown returned.
- **Troubleshooting doc:** GPU not visible in container, vLLM OOM, nightly-image
  breakage (fallback to transformers backend), Paddle-CPU issues, model download
  failures, proxy/NO_PROXY mistakes.

## Deliverables

- `compose.yaml`, `gateway/` (FastAPI app + Dockerfile), `.env.example`,
  glmocr `config.yaml`
- `client/ocr_client.py` + curl examples
- `README.md` — install, run, use, maintain, troubleshoot
- Sample test PDF + image and a verification script

## Known Risks / Mitigations

- **New model (Jan 2026)** needs nightly vLLM + transformers from source. Pin the
  working nightly by digest; fall back to the transformers backend if a nightly
  breaks.
- **WSL2 GPU in Docker** requires nvidia-container-toolkit configured for the WSL
  Docker engine. Verify with an `nvidia-smi` test container before deploying vLLM.
- **PaddlePaddle (CPU)** install can be heavy; pin a known-good version. Fallback
  is acceptable since layout runs on CPU only.
- **Proxy/NO_PROXY** misconfiguration could route internal traffic through the
  corporate proxy or block downloads. Explicitly set both in compose.
