# GLM-OCR Self-Hosted LAN Service

Self-hosted [`zai-org/GLM-OCR`](https://huggingface.co/zai-org/GLM-OCR) on a WSL2 + GPU
PC as a Docker Compose stack. Upload a PDF or image over the LAN; get back Markdown
(with LaTeX) as a JSON envelope.

## Overview

Two containers in one Compose stack:

- **`vllm`** — serves GLM-OCR (0.9B, BF16) on the GPU, OpenAI-compatible. **Internal only**, never published.
- **`gateway`** — a FastAPI app, the **only published port** (`:8080`). Validates the API
  key, counts/caps pages, rasterizes PDFs, runs PP-DocLayout-V3 layout on CPU + region
  OCR against `vllm`, and returns the envelope.

The two share an `ocr-scratch` volume so vLLM can read rasterized page images by local path.

### API contract

`POST /ocr` — multipart field `file`, header `X-API-Key` required.

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

Error codes: `401` bad/missing key · `413` over `MAX_PAGES` · `415` unsupported type ·
`503` queue full or vLLM not ready.

## Requirements

- WSL2 Ubuntu with an NVIDIA GPU (developed on RTX 4000 SFF Ada, 20 GB).
- Recent NVIDIA Windows driver (provides the WSL CUDA driver).
- Docker Engine + `nvidia-container-toolkit` inside WSL.
- Confirm GPU passthrough:

  ```bash
  docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
  ```

  The GPU must appear. If not, configure the toolkit (see Troubleshooting).

## Install

```bash
# Docker + nvidia-container-toolkit (Ubuntu/WSL2)
curl -fsSL https://get.docker.com | sh
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker && sudo service docker restart

# Generate a .env with a fresh random API key (chmod 600).
bash scripts/gen_env.sh
```

Edit `.env` to set your corporate `http_proxy` / `NO_PROXY` (the template ships with a
sensible LAN default). **Keep `.env` secret — it is git-ignored.**

## Run

```bash
docker compose up -d --build
```

First start is slow: vLLM downloads the GLM-OCR weights and the PaddlePaddle layout
weights into named volumes. Watch progress:

```bash
docker compose logs -f vllm     # wait for "Application startup complete"
until curl -fsS http://127.0.0.1:8080/health; do sleep 5; done
# {"status":"ok","vllm":true}
```

## Use

curl:

```bash
source .env
curl -fsS -H "X-API-Key: ${API_KEY}" -F "file=@scan.pdf" http://127.0.0.1:8080/ocr
```

Bundled client:

```bash
python client/ocr_client.py --host <host-ip>:8080 --key "$API_KEY" --file scan.pdf
```

End-to-end smoke against a running stack (posts the sample fixtures):

```bash
bash scripts/verify.sh            # -> VERIFY OK
```

## Maintain

- **Named volumes:** `hf-cache` (GLM-OCR / HF model weights), `paddle-cache`
  (PP-DocLayout-V3 weights), `ocr-scratch` (transient page images). Persist across
  restarts. Remove with `docker compose down -v` (forces a re-download).
- **Re-pin the vLLM image:** the nightly is pinned by digest. To update:

  ```bash
  docker compose pull vllm                       # or pull a fresh nightly tag
  docker inspect --format '{{index .RepoDigests 0}}' vllm/vllm-openai:nightly
  # paste the vllm/vllm-openai@sha256:... digest into compose.yaml -> vllm.image
  docker compose up -d vllm
  ```

- **Reboot behavior:** both services are `restart: unless-stopped`, so the stack comes
  back automatically once the Docker engine starts.

## Security

- The shared `API_KEY` is the only credential. Keep `.env` secret; never commit a real key.
- Only `:8080` (gateway) is published. vLLM is internal to the `ocrnet` Docker network.
- Scope `:8080` to the LAN. On the Windows host, restrict the firewall rule and forward
  the WSL port:

  ```powershell
  netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8080 `
        connectaddress=<wsl-ip> connectport=8080
  netsh advfirewall firewall add rule name="glm-ocr 8080" dir=in action=allow `
        protocol=TCP localport=8080 remoteip=<lan-subnet>
  ```

- **HTTPS upgrade path:** if the LAN becomes untrusted, put a TLS reverse proxy
  (Caddy / nginx) in front of `:8080` and publish only the proxy.

## Troubleshooting

- **GPU not visible in container** — re-run the `nvidia-smi` test above. Reconfigure the
  toolkit (`sudo nvidia-ctk runtime configure --runtime=docker && sudo service docker
  restart`); confirm a recent NVIDIA Windows driver.
- **vLLM OOM** — lower `--max-model-len` in `compose.yaml` (e.g. 4096).
- **Nightly image breakage** — pin back to a known-good digest, or fall back to the
  transformers backend. Re-pin per the Maintain steps once a good nightly is found.
- **Paddle CPU install issues** — pin a known-good `paddlepaddle` version in
  `gateway/Dockerfile`.
- **Model download failures** — check `http_proxy` reachability and that Hugging Face is
  reachable through it. Internal `vllm` traffic must skip the proxy.
- **Proxy / `NO_PROXY` mistakes** — `NO_PROXY` must include `vllm` (and `localhost`,
  `127.0.0.1`, your LAN subnet) so gateway↔vLLM traffic never hits the proxy.
- **`503` from `/health`** — vLLM is still loading weights; wait and retry.
- **LAN client hangs** — check the Windows Firewall rule and the `netsh interface
  portproxy` forwarding above.

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
