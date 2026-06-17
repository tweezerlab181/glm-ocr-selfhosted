from typing import Protocol

from app.config import Settings


class OCREngine(Protocol):
    def parse(self, image_paths: list[str]) -> str:
        """Return assembled Markdown for the given ordered page images."""
        ...


class GlmOcrEngine:
    """Drives the glmocr Python API: PP-DocLayout-V3 layout on CPU + region OCR
    against the vLLM OpenAI-compatible endpoint. The image list is treated as the
    pages of one document and assembled into a single Markdown string.

    NOTE FOR IMPLEMENTER (verify against the installed glmocr SDK during Task 9):
    confirm the exact import path and parser entrypoint. The shape below matches
    the SDK's documented config-driven parser; adjust names if the installed
    version differs, keeping this `parse(image_paths) -> str` signature intact.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._parser = None

    def _ensure_parser(self):
        if self._parser is None:
            from glmocr import GLMOCRParser  # heavy import, deferred
            self._parser = GLMOCRParser.from_config(
                config_path="/app/config/glmocr.config.yaml",
            )
        return self._parser

    def parse(self, image_paths: list[str]) -> str:
        parser = self._ensure_parser()
        result = parser.parse(image_paths)  # list = pages of one document
        # The SDK returns per-page markdown; join into one document.
        if isinstance(result, str):
            return result
        pages = [getattr(p, "markdown", str(p)) for p in result]
        return "\n\n".join(pages)
