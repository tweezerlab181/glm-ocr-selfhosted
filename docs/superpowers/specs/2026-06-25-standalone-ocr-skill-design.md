# Standalone OCR Skill Design

## Goal

Make the `ocr` agent skill usable from any working directory. The skill remains a
gateway client only: it submits a local PDF or image to an already running local
or LAN GLM-OCR gateway and writes the returned Markdown beside the source file.

## Non-Goals

- Do not start Docker, vLLM, or the gateway from the skill.
- Do not bundle model weights or server dependencies with the skill.
- Do not require the original repository checkout at runtime.
- Do not print API keys or copy secrets during install.

## Runtime Contract

The runner depends only on Python 3 standard library modules. It sends a
multipart `POST` request to the gateway OCR endpoint with:

- form field `file`
- header `X-API-Key`
- response JSON containing a string `markdown` field

The default endpoint is `http://127.0.0.1:8080/ocr`.

## Configuration

The runner resolves connection settings in this order:

1. CLI flags: `--url`, `--host`, `--key`, `--output`, `--timeout`
2. Environment variables:
   - endpoint: `OCR_URL`
   - host: `OCR_HOST`, `GLM_OCR_HOST`, `SERVER_LAN_IP`
   - key: `OCR_API_KEY`, `API_KEY`
3. Env files from the current working directory:
   - `.secrets/credentials.env`
   - `.env`
4. User-level env files:
   - `~/.config/glm-ocr/credentials.env`
   - `~/.config/ocr/credentials.env`
5. Default host: `127.0.0.1:8080`

Explicit process environment values win over env-file values. Env files may set
only known OCR variables. Secret values are never printed.

## Portable Path Behavior

The runner resolves the input path from the caller's current working directory,
expands `~`, and verifies that the input is a file. The default output path is a
sibling Markdown file with the final extension replaced by `.md`.

No runtime code searches for the repository root or imports from `client/`,
`gateway/`, `compose.yaml`, or repo-local `.env` files unless the caller is
actually running from that directory.

## Documentation

`skills/ocr/SKILL.md` documents standalone usage, setup requirements, config
precedence, examples for Codex and Claude installs, and the server contract.

`README.md` keeps the repo install instructions but makes clear that the
installed skill is standalone after the `skills/ocr` directory is copied.

## Testing

Add focused tests for:

- arbitrary current working directory execution
- user-level config fallback
- `OCR_URL` support and precedence over host values
- CLI flags overriding env-file values
- existing host normalization and sibling output behavior

Existing tests continue to cover multipart request construction and Markdown
output.
