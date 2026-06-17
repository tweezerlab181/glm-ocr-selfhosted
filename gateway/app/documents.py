from pathlib import Path

import pypdfium2 as pdfium

PDF_MIMES = {"application/pdf"}
IMAGE_MIMES = {
    "image/png", "image/jpeg", "image/jpg", "image/webp",
    "image/tiff", "image/bmp",
}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}


class UnsupportedType(Exception):
    pass


def detect_kind(content_type: str | None, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    ct = (content_type or "").lower()
    if ct in PDF_MIMES or ext == ".pdf":
        return "pdf"
    if ct in IMAGE_MIMES or ext in IMAGE_EXTS:
        return "image"
    raise UnsupportedType(f"unsupported type: content_type={content_type!r} ext={ext!r}")


def count_pages(data: bytes, kind: str) -> int:
    if kind == "image":
        return 1
    pdf = pdfium.PdfDocument(data)
    try:
        return len(pdf)
    finally:
        pdf.close()


def rasterize(data: bytes, kind: str, dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if kind == "image":
        out = dest_dir / "page-0001.img"
        out.write_bytes(data)
        return [out]

    pdf = pdfium.PdfDocument(data)
    paths: list[Path] = []
    try:
        for i in range(len(pdf)):
            bitmap = pdf[i].render(scale=2.0)
            image = bitmap.to_pil()
            out = dest_dir / f"page-{i + 1:04d}.png"
            image.save(out)
            paths.append(out)
        return paths
    finally:
        pdf.close()
