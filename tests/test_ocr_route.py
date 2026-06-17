import tempfile

import pytest
from fastapi.testclient import TestClient

from app.concurrency import ConcurrencyGate, QueueFull
from app.config import Settings
from app.main import create_app

HEADERS = {"X-API-Key": "secret"}
SCRATCH = tempfile.mkdtemp()


class FakeEngine:
    def parse(self, image_paths):
        return "# Page\n\n$E = mc^2$"


def client(engine=None, gate=None, health=True, max_pages=50):
    settings = Settings(api_key="secret", max_pages=max_pages, scratch_dir=SCRATCH)
    return TestClient(create_app(
        settings=settings,
        engine=engine or FakeEngine(),
        gate=gate or ConcurrencyGate(1, 8),
        health_check=lambda: health,
    ))


def test_ocr_requires_key(sample_png):
    c = client()
    r = c.post("/ocr", files={"file": ("a.png", sample_png.read_bytes(), "image/png")})
    assert r.status_code == 401


def test_ocr_happy_path(sample_png):
    c = client()
    r = c.post("/ocr", headers=HEADERS,
               files={"file": ("a.png", sample_png.read_bytes(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "a.png"
    assert body["pages"] == 1
    assert "mc^2" in body["markdown"]
    assert isinstance(body["elapsed_sec"], (int, float))


def test_ocr_unsupported_type():
    c = client()
    r = c.post("/ocr", headers=HEADERS,
               files={"file": ("a.zip", b"PK\x03\x04", "application/zip")})
    assert r.status_code == 415


def test_ocr_over_page_cap(sample_pdf):
    c = client(max_pages=0)  # any PDF exceeds 0
    r = c.post("/ocr", headers=HEADERS,
               files={"file": ("a.pdf", sample_pdf.read_bytes(), "application/pdf")})
    assert r.status_code == 413


def test_ocr_queue_full(sample_png):
    class FullGate(ConcurrencyGate):
        def slot(self):
            raise QueueFull()
    c = client(gate=FullGate(1, 0))
    r = c.post("/ocr", headers=HEADERS,
               files={"file": ("a.png", sample_png.read_bytes(), "image/png")})
    assert r.status_code == 503


def test_health_ok():
    assert client(health=True).get("/health").json()["vllm"] is True


def test_health_degraded():
    r = client(health=False).get("/health")
    assert r.status_code == 503 and r.json()["vllm"] is False
