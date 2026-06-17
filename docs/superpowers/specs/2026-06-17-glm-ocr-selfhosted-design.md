# GLM-OCR Self-Hosted LAN Service — Design

**Date:** 2026-06-17
**Status:** Approved (design phase)
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

## Model Choice

**`zai-org/GLM-OCR`** — 0.9B parameters, MIT license, released 2026-01-27.

Rationale:
- Purpose-built document OCR. Tops OmniDocBench V1.5 with 94.62, beating general
  VLMs up to 235B parameters.
- 0.9B → roughly 2 GB VRAM in BF16. Fits the 20 GB GPU with large headroom for
  context length and concurrency. Full BF16 quality costs nothing here, so no
  quantization needed.
- ~1.86 pages/second PDF throughput.
- Native vLLM OpenAI-compatible serving. Outputs Markdown with LaTeX formula and
  table recognition.

Tradeoffs:
- vs larger (e.g. GLM-4.5V 9B): general VLM, ~18 GB BF16, slower, weaker on pure
  document OCR, no reasoning benefit for OCR. Rejected.
- vs smaller / llama.cpp INT4 quants: unnecessary — a dedicated GPU is present, so
  full-precision BF16 is the higher-quality, no-cost choice. Rejected.

## Architecture

Three containers in one Docker Compose stack:

1. **vllm** — serves `zai-org/GLM-OCR` (BF16), OpenAI-compatible API on internal
   port 8080, GPU access via nvidia-container-toolkit. Flags: `--max-model-len 8192`,
   MTP speculative decoding, `--allowed-local-media-path`. Not exposed to LAN.
2. **glmocr** — official glmocr SDK `[selfhosted]` Flask server on internal port
   8000. Performs layout analysis (PP-DocLayout-V3), PDF preprocessing
   (PageLoader), parallel region OCR by calling the vllm service, and Markdown /
   LaTeX assembly. Not exposed to LAN.
3. **caddy** — reverse proxy. The only LAN-exposed port. Enforces an `X-API-Key`
   header, then forwards to the glmocr service. Binds `0.0.0.0`.

### Data flow

```
LAN client ──POST file + X-API-Key──> caddy:<LANport>
                                         │
                                         ▼
                                   glmocr:8000  (layout + OCR + assemble)
                                         │ OpenAI API
                                         ▼
                                   vllm:8080   (GLM-OCR inference on GPU)
                                         │
                            Markdown / LaTeX ◀── returned to client
```

## Components and Responsibilities

- **vllm container**: inference only. Input = chat-completions requests with image
  content. Output = recognized text. Depends on the GPU and the downloaded model.
- **glmocr container**: orchestration. Input = uploaded PDF/image file. Output =
  assembled Markdown/LaTeX document. Depends on vllm being healthy.
- **caddy container**: security gateway. Input = LAN HTTP request. Output =
  proxied response or 401. Depends on glmocr.
- **client example** (`ocr_client.py` + curl): off-box usage. Input = a file +
  API key + server address. Output = saved Markdown.

## Persistence

- HuggingFace model cache on a named Docker volume — model downloaded once,
  survives container recreation.
- All services `restart: unless-stopped`.
- Docker (with the stack) starts when WSL/Docker starts, so the service comes back
  after reboot without manual steps.

## Security

- API key stored in `.env` (git-ignored); Caddy rejects requests without a valid
  `X-API-Key`.
- Only the Caddy port is published to the host/LAN; vllm and glmocr stay on the
  internal Compose network.
- Documented firewall guidance to scope the published port to the LAN subnet.
- Plain HTTP, justified by a trusted LAN. Documented upgrade path to self-signed
  HTTPS (Caddy can issue internal certs) if the network becomes untrusted.

## Output Handling

- Markdown is the primary output; embedded math returned as LaTeX (`$...$` /
  `$$...$$`) per GLM-OCR formula recognition. Tables as Markdown/HTML per SDK.
- API returns Markdown body plus metadata (page count, timing). Multi-page PDFs
  assembled into one document (SDK treats image list as pages of one document).

## Testing Strategy

- **Unit**: PDF→image rasterization sanity; API-key rejection (401 without key).
- **Integration**: feed a sample PDF and a sample image, assert non-empty Markdown
  and that a known formula/table is present.
- **LAN smoke**: from a second PC, run the client against `<host-ip>:<port>` with
  the key; confirm Markdown returned.
- **Troubleshooting doc**: GPU not visible in container, vLLM OOM, nightly-image
  breakage (fallback to transformers backend), model download failures.

## Deliverables

- `compose.yaml`, `Caddyfile`, `.env.example`, glmocr `config.yaml`
- `client/ocr_client.py` + curl examples
- `README.md` — install, run, use, maintain, troubleshoot
- Sample test PDF + image and a verification script

## Known Risks / Mitigations

- **New model (Jan 2026)** may require nightly/dev vLLM and SGLang builds. Pin
  working image tags during implementation; fall back to the transformers backend
  if a nightly build is broken.
- **WSL2 GPU in Docker** requires nvidia-container-toolkit configured for the WSL
  Docker engine. Verify with a `nvidia-smi` test container before deploying vLLM.
- **VRAM**: 0.9B model is comfortable, but `--gpu-memory-utilization` will be
  tuned so the layout model and OS overhead coexist.
