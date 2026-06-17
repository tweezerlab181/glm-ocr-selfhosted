import httpx

from app.config import Settings


async def vllm_ready(settings: Settings) -> bool:
    url = f"{settings.vllm_url.rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(url)
            return resp.status_code == 200
    except Exception:
        return False
