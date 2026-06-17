import pytest

from app.documents import UnsupportedType, count_pages, detect_kind, rasterize


def test_detect_pdf_by_mime():
    assert detect_kind("application/pdf", "x.bin") == "pdf"


def test_detect_image_by_extension():
    assert detect_kind(None, "scan.PNG") == "image"


def test_detect_unsupported():
    with pytest.raises(UnsupportedType):
        detect_kind("application/zip", "x.zip")


def test_count_pages_image_is_one(sample_png):
    assert count_pages(sample_png.read_bytes(), "image") == 1


def test_count_pages_pdf(sample_pdf):
    assert count_pages(sample_pdf.read_bytes(), "pdf") >= 1


def test_rasterize_pdf_writes_pages(tmp_path, sample_pdf):
    paths = rasterize(sample_pdf.read_bytes(), "pdf", tmp_path)
    assert len(paths) >= 1
    assert all(p.exists() and p.stat().st_size > 0 for p in paths)


def test_rasterize_image_passthrough(tmp_path, sample_png):
    paths = rasterize(sample_png.read_bytes(), "image", tmp_path)
    assert len(paths) == 1 and paths[0].exists()
