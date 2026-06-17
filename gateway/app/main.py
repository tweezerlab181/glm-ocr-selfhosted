import tempfile
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.auth import require_api_key
from app.concurrency import ConcurrencyGate, QueueFull
from app.config import Settings, get_settings
from app.documents import UnsupportedType, count_pages, detect_kind, rasterize
from app.health import vllm_ready
from app.ocr_engine import GlmOcrEngine, OCREngine


def create_app(
    settings: Settings | None = None,
    engine: OCREngine | None = None,
    gate: ConcurrencyGate | None = None,
    health_check=None,
) -> FastAPI:
    settings = settings or get_settings()
    engine = engine or GlmOcrEngine(settings)
    gate = gate or ConcurrencyGate(settings.max_concurrency, settings.queue_max)
    health_check = health_check or (lambda: None)  # None sentinel -> real probe

    app = FastAPI(title="GLM-OCR Gateway")
    # Auth and other deps resolve get_settings; bind it to this app's settings.
    app.dependency_overrides[get_settings] = lambda: settings

    async def _is_ready() -> bool:
        result = health_check()
        if result is None:
            return await vllm_ready(settings)
        return bool(result)

    @app.get("/health")
    async def health():
        ready = await _is_ready()
        body = {"status": "ok" if ready else "degraded", "vllm": ready}
        if not ready:
            return JSONResponse(status_code=503, content=body)
        return body

    @app.post("/ocr", dependencies=[Depends(require_api_key)])
    async def ocr(file: UploadFile = File(...)):
        data = await file.read()
        try:
            kind = detect_kind(file.content_type, file.filename or "")
        except UnsupportedType as exc:
            raise HTTPException(status_code=415, detail=str(exc))

        pages = count_pages(data, kind)
        if pages > settings.max_pages:
            raise HTTPException(
                status_code=413,
                detail=f"{pages} pages exceeds MAX_PAGES={settings.max_pages}",
            )

        try:
            async with gate.slot():
                started = time.perf_counter()
                with tempfile.TemporaryDirectory(dir=settings.scratch_dir) as tmp:
                    image_paths = rasterize(data, kind, Path(tmp))
                    markdown = await run_in_threadpool(
                        engine.parse, [str(p) for p in image_paths]
                    )
                elapsed = round(time.perf_counter() - started, 3)
        except QueueFull:
            raise HTTPException(status_code=503, detail="OCR queue is full; retry later")

        return {
            "markdown": markdown,
            "pages": pages,
            "elapsed_sec": elapsed,
            "filename": file.filename,
        }

    return app
