#!/usr/bin/env python3
"""Run GLM-OCR against a local PDF/image and write sibling Markdown."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ENV_FILES = (".secrets/credentials.env", ".env")
USER_ENV_FILES = (
    Path("~/.config/glm-ocr/credentials.env"),
    Path("~/.config/ocr/credentials.env"),
)
KNOWN_ENV_KEYS = {
    "API_KEY",
    "OCR_API_KEY",
    "OCR_HOST",
    "GLM_OCR_HOST",
    "SERVER_LAN_IP",
    "OCR_URL",
}


def default_output_path(source: Path) -> Path:
    return source.with_suffix(".md")


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in KNOWN_ENV_KEYS:
            continue
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def load_env_files(start_dir: Path) -> None:
    for rel_path in ENV_FILES:
        load_env_file(start_dir / rel_path)
    for env_path in USER_ENV_FILES:
        load_env_file(env_path.expanduser())


def endpoint_from(host: str | None, url: str | None = None) -> str:
    if url:
        return safe_http_url(url.rstrip("/"))
    host = host or "127.0.0.1:8080"
    if host.startswith(("http://", "https://")):
        return safe_http_url(f"{host.rstrip('/')}/ocr")
    if "://" in host:
        raise ValueError("OCR host URL must use http or https")
    if ":" not in host:
        host = f"{host}:8080"
    return f"http://{host.rstrip('/')}/ocr"


def safe_http_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("OCR URL must use http or https")
    return url


def build_multipart(source: Path) -> tuple[bytes, str]:
    boundary = f"----glm-ocr-{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            (
                'Content-Disposition: form-data; name="file"; '
                f'filename="{source.name}"\r\n'
            ).encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            source.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    return body, f"multipart/form-data; boundary={boundary}"


def post_ocr(source: Path, endpoint: str, api_key: str, timeout: float) -> dict:
    endpoint = safe_http_url(endpoint)
    body, content_type = build_multipart(source)
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "X-API-Key": api_key,
            "Content-Type": content_type,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            response_body = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OCR request failed: HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OCR request failed: {exc.reason}") from exc

    if status != 200:
        raise RuntimeError(f"OCR request failed: HTTP {status}: {response_body!r}")
    try:
        return json.loads(response_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("OCR response was not valid JSON") from exc


def run_ocr(
    source: Path,
    host: str | None = None,
    api_key: str | None = None,
    output: Path | None = None,
    url: str | None = None,
    timeout: float = 600.0,
) -> Path:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Input file not found: {source}")

    process_env = os.environ.copy()
    load_env_files(Path.cwd())
    api_key = (
        api_key
        or process_env.get("OCR_API_KEY")
        or process_env.get("API_KEY")
        or os.environ.get("OCR_API_KEY")
        or os.environ.get("API_KEY")
    )
    host = (
        host
        or process_env.get("OCR_HOST")
        or process_env.get("GLM_OCR_HOST")
        or process_env.get("SERVER_LAN_IP")
        or os.environ.get("OCR_HOST")
        or os.environ.get("GLM_OCR_HOST")
        or os.environ.get("SERVER_LAN_IP")
    )
    url = url or process_env.get("OCR_URL") or os.environ.get("OCR_URL")
    if not api_key:
        raise RuntimeError("Missing API key. Set OCR_API_KEY/API_KEY or pass --key.")

    output_path = (output or default_output_path(source)).expanduser().resolve()
    payload = post_ocr(source, endpoint_from(host, url), api_key, timeout)
    markdown = payload.get("markdown")
    if not isinstance(markdown, str):
        raise RuntimeError("OCR response JSON does not contain string field 'markdown'")

    output_path.write_text(markdown.rstrip() + "\n", encoding="utf-8")
    return output_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run GLM-OCR on a PDF/image and save Markdown next to it.",
    )
    parser.add_argument("file", help="PDF or image path")
    parser.add_argument("--host", help="Gateway host, e.g. 127.0.0.1:8080")
    parser.add_argument("--url", help="Full OCR endpoint URL, overrides --host")
    parser.add_argument("--key", help="API key; defaults to OCR_API_KEY or API_KEY")
    parser.add_argument("--output", help="Markdown output path; defaults to FILE_STEM.md")
    parser.add_argument("--timeout", type=float, default=600.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        output = run_ocr(
            Path(args.file),
            host=args.host,
            api_key=args.key,
            output=Path(args.output) if args.output else None,
            url=args.url,
            timeout=args.timeout,
        )
    except Exception as exc:
        print(f"ocr error: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
