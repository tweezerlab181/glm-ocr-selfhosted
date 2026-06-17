import httpx
import pytest

from app.config import Settings
from app.health import vllm_ready


@pytest.mark.asyncio
async def test_vllm_ready_true(monkeypatch):
    async def fake_get(self, url, **kw):
        return httpx.Response(200, json={"data": []})
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await vllm_ready(Settings(api_key="k")) is True


@pytest.mark.asyncio
async def test_vllm_ready_false_on_error(monkeypatch):
    async def fake_get(self, url, **kw):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await vllm_ready(Settings(api_key="k")) is False
