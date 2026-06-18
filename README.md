# GLM-OCR Self-Hosted LAN Service

Self-hosted [`zai-org/GLM-OCR`](https://huggingface.co/zai-org/GLM-OCR) on a WSL2 + GPU
PC as a Docker Compose stack. Any machine on the LAN uploads a PDF or image over HTTP
and gets back Markdown (with LaTeX formulas and tables) as a JSON envelope.

## Overview

Two containers in one Compose stack:

- **`vllm`** — serves GLM-OCR (0.9B, BF16) on the GPU, OpenAI-compatible. **Internal only**, never published.
- **`gateway`** — a FastAPI app, the **only published port** (`:8080`). Validates the API
  key, counts/caps pages, rasterizes PDFs, runs PP-DocLayout-V3 layout on CPU + region
  OCR against `vllm`, and returns the envelope.

The two share an `ocr-scratch` volume so vLLM can read rasterized page images by local path.

### API contract

`POST /ocr` — multipart field `file` (PDF or image), header `X-API-Key` required → `200`:

```json
{
  "markdown": "# ...",
  "pages": 3,
  "elapsed_sec": 4.21,
  "filename": "scan.pdf"
}
```

`GET /health` (no auth) → `200 {"status":"ok","vllm":true}` when vLLM is reachable,
else `503 {"status":"degraded","vllm":false}`.

Error codes: `401` bad/missing key · `413` over `MAX_PAGES` (default 50) · `415`
unsupported type · `503` queue full or vLLM not ready.

---

## Requirements (server PC)

- Windows host with WSL2 Ubuntu and an NVIDIA GPU (developed on RTX 4000 SFF Ada, 20 GB).
- Recent NVIDIA Windows driver (provides the WSL CUDA driver).
- Docker Engine + `nvidia-container-toolkit` inside WSL.
- ~10 GB disk for model weights (downloaded once into named volumes).

---

## Server PC — initialization (one-time)

Run everything below **inside the WSL Ubuntu shell** on the server PC.

### 1. Install Docker + NVIDIA container toolkit

```bash
# Docker Engine
curl -fsSL https://get.docker.com | sh

# NVIDIA container toolkit (GPU passthrough into containers)
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker && sudo service docker restart
```

### 2. Confirm GPU passthrough

```bash
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

Your GPU must appear. If not, see [Troubleshooting](#troubleshooting).

### 3. Get the code and generate an API key

```bash
git clone https://github.com/tweezerlab181/glm-ocr-selfhosted.git
cd glm-ocr-selfhosted
bash scripts/gen_env.sh          # writes .env with a fresh random key (chmod 600)
```

`.env` is git-ignored and holds your shared `API_KEY`. Open it and, **only if your
network requires a proxy**, set `http_proxy` / `NO_PROXY` (the template default works
for a direct-internet LAN). `NO_PROXY` must always include `vllm`, `localhost`,
`127.0.0.1`, and your LAN subnet so internal traffic never routes through a proxy.

### 4. Bring up the stack

```bash
docker compose up -d --build
```

First start is slow — vLLM downloads the GLM-OCR weights and the PP-DocLayout-V3 layout
weights into named volumes (one time). Wait for readiness:

```bash
docker compose logs -f vllm                 # wait for "Application startup complete"
until curl --noproxy '*' -fsS http://127.0.0.1:8080/health; do sleep 5; done
# {"status":"ok","vllm":true}
```

### 5. Local smoke test

```bash
bash scripts/verify.sh           # -> VERIFY OK  (posts the sample PDF + image)
```

### 6. Expose to the LAN

By default WSL2 uses NAT, so the stack is only reachable on the server PC itself.
To let **other PCs** reach it, pick one:

**Option A — mirrored networking (recommended, survives reboots).**
On the Windows host, create/edit `C:\Users\<you>\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
```

Then in a **Windows** terminal: `wsl --shutdown` (wait ~15s, reopen WSL). The server's
LAN IP now forwards to WSL automatically. The stack auto-restarts (`restart:
unless-stopped`); if not, `docker compose up -d`.

**Option B — port-forward (per-reboot).**
In an **Administrator** PowerShell on Windows (`<WSL_IP>` from `hostname -I` in WSL):

```powershell
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8080 `
      connectaddress=<WSL_IP> connectport=8080
```
Re-run after each reboot (the WSL IP changes).

**Firewall (both options).** Allow inbound `:8080`, scoped to your LAN subnet:

```powershell
netsh advfirewall firewall add rule name="glm-ocr 8080" dir=in action=allow `
      protocol=TCP localport=8080 remoteip=<LAN_SUBNET>
```

Find the server's LAN IP with `ipconfig` (Windows) — call it `<SERVER_LAN_IP>` below.

---

## Server PC — operation

```bash
docker compose ps                # status (gateway should be "healthy")
docker compose logs -f gateway   # gateway logs
docker compose logs -f vllm      # model server logs
docker compose restart gateway   # restart one service
docker compose down              # stop the stack (volumes kept)
docker compose up -d             # start again
```

---

## Client PC — usage

Any LAN machine. You need two things from the server operator:

- `<SERVER_LAN_IP>` — the server PC's LAN address.
- `<KEY>` — the API key (on the server: `grep API_KEY .env`).

> If your client PC sits behind a corporate proxy, bypass it for the server — the
> examples use `curl --noproxy '*'` / `NO_PROXY=<SERVER_LAN_IP>`. Otherwise the proxy
> intercepts the request and you get an HTML proxy error instead of JSON.

### Check the server is reachable

```bash
curl --noproxy '*' http://<SERVER_LAN_IP>:8080/health
# {"status":"ok","vllm":true}
```

### OCR a file and save the Markdown

The result is returned in the HTTP response — **nothing is stored on the server**. You
save it on the client:

```bash
curl --noproxy '*' -H "X-API-Key: <KEY>" -F "file=@/path/to/your.pdf" \
     http://<SERVER_LAN_IP>:8080/ocr \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['markdown'])" > out.md
```

`out.md` lands in your current directory. PDF or image both work; a multi-page PDF
becomes one combined Markdown document.

### Want the full envelope (markdown + pages + timing)

```bash
curl --noproxy '*' -H "X-API-Key: <KEY>" -F "file=@/path/to/your.pdf" \
     http://<SERVER_LAN_IP>:8080/ocr -o result.json
```

### Bundled Python client

If the client PC has Python + httpx and a copy of `client/ocr_client.py`:

```bash
NO_PROXY=<SERVER_LAN_IP> python ocr_client.py \
     --host <SERVER_LAN_IP>:8080 --key <KEY> --file your.pdf > out.md
```

Prints Markdown to stdout (redirect to a file), progress to stderr; non-zero exit on error.

### Agent OCR skill (`$ocr` / `/ocr`)

This repo also ships an agent skill that calls the same `/ocr` gateway and writes the
Markdown next to the source file. The skill is useful when working inside Codex or
Claude Code and you want:

```text
source: /path/to/paper.pdf
output: /path/to/paper.md
```

Install it on a client machine that can reach the gateway:

```bash
bash scripts/install_ocr_skill.sh
```

By default the installer copies:

- `skills/ocr` -> `${CODEX_HOME:-$HOME/.codex}/skills/ocr`, making `$ocr` available in Codex.
- `skills/ocr` -> `${CLAUDE_HOME:-$HOME/.claude}/skills/ocr`.
- `claude/commands/ocr.md` -> `${CLAUDE_HOME:-$HOME/.claude}/commands/ocr.md`, making `/ocr` available in Claude Code.

Install only one target when needed:

```bash
bash scripts/install_ocr_skill.sh --codex-only
bash scripts/install_ocr_skill.sh --claude-only
bash scripts/install_ocr_skill.sh --dry-run
```

Configure credentials in the shell that runs the agent:

```bash
export OCR_HOST=<SERVER_LAN_IP>:8080
export OCR_API_KEY=<KEY>
```

The runner also accepts `API_KEY`, `GLM_OCR_HOST`, `--host`, `--url`, `--key`, and
`--output`. If env vars are not set, it will read `.secrets/credentials.env` or `.env`
from the current directory, but it never prints secret values.

Usage:

```text
Codex:  $ocr /path/to/your.pdf
Claude: /ocr /path/to/your.pdf
```

Direct runner usage:

```bash
python3 ~/.codex/skills/ocr/scripts/run_ocr.py /path/to/your.pdf
python3 ~/.claude/skills/ocr/scripts/run_ocr.py /path/to/your.png
```

On success, the command prints the Markdown path and writes the OCR text to a sibling
`.md` file derived from the source filename.

### Limits & errors

- Max 50 pages per request (`413` if exceeded — raise `MAX_PAGES` in the server `.env`).
- One OCR job at a time; extra requests queue, `503` when the queue is full.
- `401` = missing/wrong key · `415` = unsupported file type.

---

## Maintain

- **Named volumes:** `hf-cache` (GLM-OCR / HF model weights), `paddle-cache`
  (PP-DocLayout-V3 weights), `ocr-scratch` (transient page images). Persist across
  restarts. Remove with `docker compose down -v` (forces a re-download).
- **Re-pin the vLLM image:** the nightly is pinned by digest in `compose.yaml`. To update:

  ```bash
  docker compose pull vllm
  docker inspect --format '{{index .RepoDigests 0}}' vllm/vllm-openai:nightly
  # paste the vllm/vllm-openai@sha256:... digest into compose.yaml -> vllm.image
  docker compose up -d vllm
  ```

- **Reboot behavior:** both services are `restart: unless-stopped`, so the stack comes
  back automatically once the Docker engine starts.

## Security

- The shared `API_KEY` is the only credential. Keep `.env` secret; never commit a real
  key (it is git-ignored). Rotate by regenerating and restarting the gateway.
- Only `:8080` (gateway) is published. vLLM stays internal to the `ocrnet` Docker network.
- Scope the firewall rule to your LAN subnet (see [step 6](#6-expose-to-the-lan)).
- Plain HTTP, justified by a trusted LAN. **HTTPS upgrade path:** if the network becomes
  untrusted, put a TLS reverse proxy (Caddy / nginx) in front of `:8080` and publish only
  the proxy.

## Troubleshooting

- **GPU not visible in container** — re-run the `nvidia-smi` test. Reconfigure the toolkit
  (`sudo nvidia-ctk runtime configure --runtime=docker && sudo service docker restart`);
  confirm a recent NVIDIA Windows driver.
- **vLLM OOM** — lower `--max-model-len` in `compose.yaml` (e.g. 4096).
- **Nightly image breakage** — pin back to a known-good digest, or fall back to the
  transformers backend. Re-pin per the Maintain steps once a good nightly is found.
- **Paddle CPU install issues** — pin a known-good `paddlepaddle` version in
  `gateway/Dockerfile`.
- **Model download failures** — check internet (and `http_proxy` if used); Hugging Face
  must be reachable. Internal `vllm` traffic must skip any proxy.
- **Proxy / `NO_PROXY` mistakes** — `NO_PROXY` must include `vllm`, `localhost`,
  `127.0.0.1`, and your LAN subnet so gateway↔vLLM traffic never hits the proxy.
- **Client gets an HTML page, not JSON** — the client's corporate proxy intercepted the
  request. Use `--noproxy '*'` (curl) or `NO_PROXY=<SERVER_LAN_IP>` (client script).
- **Client connection refused / hangs** — LAN exposure not set up: check the firewall rule
  and the mirrored-networking or portproxy step on the server.
- **`503` from `/health`** — vLLM is still loading weights; wait and retry.

## Development

Unit tests run in a plain venv — no model, GPU, or Docker needed (heavy `glmocr` /
`paddlepaddle` imports are deferred into `GlmOcrEngine`):

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e "gateway[dev]"
PYTHONPATH=gateway pytest tests --ignore=tests/test_integration.py
```

Integration tests run against a live stack:

```bash
source .env
RUN_INTEGRATION=1 API_KEY="$API_KEY" PYTHONPATH=gateway pytest tests/test_integration.py
```
