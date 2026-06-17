"""Generate tiny committed test fixtures. Run once: python scripts/make_fixtures.py"""
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw

out = Path(__file__).parent.parent / "tests" / "fixtures"
out.mkdir(parents=True, exist_ok=True)

img = Image.new("RGB", (320, 120), "white")
d = ImageDraw.Draw(img)
d.text((10, 40), "Hello OCR 2026  E = mc^2", fill="black")
img.save(out / "sample.png")

# Minimal one-page PDF embedding the same image.
pdf = pdfium.PdfDocument.new()
page = pdf.new_page(320, 120)
img_obj = pdfium.PdfImage.new(pdf)
img_obj.set_bitmap(pdfium.PdfBitmap.from_pil(img))
img_obj.set_matrix(pdfium.PdfMatrix(320, 0, 0, 120, 0, 0))
page.insert_obj(img_obj)
page.gen_content()
pdf.save(out / "sample.pdf")
print("wrote", out / "sample.png", "and", out / "sample.pdf")
