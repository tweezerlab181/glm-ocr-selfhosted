---
description: Run GLM-OCR on a local PDF or image and save Markdown beside it
argument-hint: <path-to-pdf-or-image>
allowed-tools: [Bash, Read]
---

# OCR

Use the installed OCR skill to process the file path supplied in `$ARGUMENTS`.

Run:

```bash
python3 ~/.claude/skills/ocr/scripts/run_ocr.py "$ARGUMENTS"
```

If the path contains quotes or multiple arguments, reconstruct the intended local file path before running the command. Report the generated Markdown path. Do not print secret values or paste the full OCR output unless the user asks.
