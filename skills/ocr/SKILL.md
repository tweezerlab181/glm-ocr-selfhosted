---
name: ocr
description: Run GLM-OCR for local PDF or image files and save extracted Markdown beside the source file. Use when the user invokes $ocr or asks to OCR, transcribe, extract text, or convert a document/image/PDF scan into Markdown with this repository's self-hosted GLM-OCR gateway.
---

# OCR

## Overview

Use the bundled runner to submit one local PDF or image to the GLM-OCR gateway and write the returned `markdown` field to a sibling `.md` file. The output path defaults to the original filename with its final extension replaced by `.md`.

## Quick Start

Run:

```bash
python3 ~/.codex/skills/ocr/scripts/run_ocr.py "/path/to/document.pdf"
```

For Claude Code installs, use:

```bash
python3 ~/.claude/skills/ocr/scripts/run_ocr.py "/path/to/document.pdf"
```

## Inputs

- Accept PDF and image files supported by the gateway.
- Accept host from `OCR_HOST`, `GLM_OCR_HOST`, or `SERVER_LAN_IP`; default to `127.0.0.1:8080`.
- Accept API key from `OCR_API_KEY` or `API_KEY`, or `--key`.
- If env vars are unset, load `.secrets/credentials.env` or `.env` from the current working directory. Never print secret values.

## Workflow

1. Resolve the user-supplied path and verify it is a file.
2. Run `scripts/run_ocr.py` with the path. Pass `--host`, `--url`, `--key`, or `--output` only when needed.
3. Report the generated Markdown file path. Do not paste the full OCR output unless the user asks.

## Examples

```bash
python3 ~/.codex/skills/ocr/scripts/run_ocr.py "./test docs/Grimm et al. - 1999 - Optical dipole traps for neutral atoms.pdf"
```

Writes `./test docs/Grimm et al. - 1999 - Optical dipole traps for neutral atoms.md`.

```bash
python3 ~/.codex/skills/ocr/scripts/run_ocr.py --host 192.168.1.20:8080 --key "$OCR_API_KEY" scan.png
```
