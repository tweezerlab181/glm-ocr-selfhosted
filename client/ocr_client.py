#!/usr/bin/env python3
"""Submit a PDF or image to the GLM-OCR gateway and print the Markdown."""
import argparse
import sys

import httpx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1:8080")
    ap.add_argument("--key", required=True)
    ap.add_argument("--file", required=True)
    args = ap.parse_args()

    url = f"http://{args.host}/ocr"
    with open(args.file, "rb") as fh:
        resp = httpx.post(
            url,
            headers={"X-API-Key": args.key},
            files={"file": (args.file.split("/")[-1], fh)},
            timeout=600.0,
        )
    if resp.status_code != 200:
        print(f"error {resp.status_code}: {resp.text}", file=sys.stderr)
        return 1
    body = resp.json()
    sys.stderr.write(f"# {body['pages']} pages in {body['elapsed_sec']}s\n")
    print(body["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
