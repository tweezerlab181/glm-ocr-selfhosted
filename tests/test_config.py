import pytest
from app.config import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("API_KEY", "k")
    s = Settings()
    assert s.api_key == "k"
    assert s.vllm_url == "http://vllm:8080/v1"
    assert s.model == "zai-org/GLM-OCR"
    assert s.max_pages == 50
    assert s.max_upload_bytes == 100 * 1024 * 1024
    assert s.max_concurrency == 1
    assert s.queue_max == 8
    assert s.scratch_dir == "/scratch"


def test_settings_requires_api_key(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    with pytest.raises(Exception):
        Settings()


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("API_KEY", "k")
    monkeypatch.setenv("MAX_PAGES", "10")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "12345")
    assert Settings().max_pages == 10
    assert Settings().max_upload_bytes == 12345
