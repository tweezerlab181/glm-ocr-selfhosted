from typing import Protocol

from app.config import Settings

CONFIG_PATH = "/app/config/glmocr.config.yaml"


class OCREngine(Protocol):
    def parse(self, image_paths: list[str]) -> str:
        """Return assembled Markdown for the given ordered page images."""
        ...


class GlmOcrEngine:
    """Drives the glmocr Python API: PP-DocLayout-V3 layout on CPU + region OCR
    against the vLLM OpenAI-compatible endpoint. The image list is treated as the
    pages of one document and assembled into a single Markdown string.

    Verified against glmocr's installed API: `GlmOcr(config_path=...)` with a
    partial YAML merged onto the SDK defaults; `.parse(images)` returns a
    `PipelineResult` (or list of them) exposing `.markdown_result`.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from glmocr import GlmOcr  # heavy import, deferred
            # mode="selfhosted" -> use the local vLLM pipeline, not the cloud MaaS API.
            self._client = GlmOcr(config_path=CONFIG_PATH, mode="selfhosted")
        return self._client

    @staticmethod
    def _markdown(result) -> str:
        md = getattr(result, "markdown_result", None)
        return md if md else ""

    def parse(self, image_paths: list[str]) -> str:
        client = self._ensure_client()
        result = client.parse(
            image_paths,  # list = pages of one document
            save_layout_visualization=False,
            preserve_order=True,
        )
        if isinstance(result, list):
            pages = [self._markdown(r) for r in result]
        else:
            pages = [self._markdown(result)]
        return "\n\n".join(p for p in pages if p)
