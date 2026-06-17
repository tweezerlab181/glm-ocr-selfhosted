import os
import subprocess

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1",
    reason="set RUN_INTEGRATION=1 with a running stack",
)

HOST = os.environ.get("OCR_HOST", "127.0.0.1:8080")
KEY = os.environ.get("API_KEY")


def _post(path: str, content_type: str):
    with open(path, "rb") as fh:
        return httpx.post(
            f"http://{HOST}/ocr",
            headers={"X-API-Key": KEY},
            files={"file": (os.path.basename(path), fh, content_type)},
            timeout=600.0,
        )


def test_image_returns_markdown(sample_png):
    r = _post(str(sample_png), "image/png")
    assert r.status_code == 200
    assert r.json()["markdown"].strip()


def test_pdf_returns_markdown(sample_pdf):
    r = _post(str(sample_pdf), "application/pdf")
    assert r.status_code == 200
    body = r.json()
    assert body["pages"] >= 1 and body["markdown"].strip()
