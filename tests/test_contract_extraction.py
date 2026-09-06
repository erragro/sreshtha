"""Unit tests for app.contracts.ocr text extraction (txt / docx / routing).

The image-OCR path (Tesseract) is exercised only when the binary + English
language data are available on the host; otherwise that test is skipped.
"""

from __future__ import annotations

import io
import shutil
import zipfile

import pytest

from app.contracts import ocr


# ---------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------


def test_extract_plain_text_utf8():
    raw = "Clause 1.\nNo minimum pay is guaranteed for any shift.".encode("utf-8")
    result = ocr.extract_text(raw, "text/plain", source_language="en")
    assert "No minimum pay" in result.text
    assert result.language == "en"


def test_extract_plain_text_utf16_and_bom():
    raw = "Security deposit is Rs. 3000, refundable after six months.".encode("utf-16")
    result = ocr.extract_text(raw, "text/plain")
    assert "Security deposit" in result.text


def test_extract_plain_text_flags_low_quality_when_tiny():
    result = ocr.extract_text(b"short", "text/plain")
    assert result.is_low_quality is True


# ---------------------------------------------------------------------------
# .docx
# ---------------------------------------------------------------------------


def _docx(*paragraphs: str) -> bytes:
    runs = "".join(
        f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs
    )
    body = (
        '<?xml version="1.0"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{runs}</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", body)
    return buf.getvalue()


def test_extract_docx_joins_paragraphs_with_newlines():
    raw = _docx(
        "DELIVERY PARTNER AGREEMENT",
        "1. The worker is an independent contractor.",
        "2. The company may deactivate the ID at any time.",
    )
    result = ocr.extract_text(raw, ocr.DOCX_MIME, source_language="en")
    lines = result.text.splitlines()
    assert lines[0] == "DELIVERY PARTNER AGREEMENT"
    assert "independent contractor" in lines[1]
    assert "deactivate the ID" in lines[2]


def test_extract_docx_unescapes_entities_and_splits_runs():
    # Word splits a sentence across multiple <w:t> runs; ampersands are escaped.
    body = (
        '<?xml version="1.0"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p>"
        "<w:r><w:t>Fees &amp; </w:t></w:r><w:r><w:t>expenses</w:t></w:r>"
        "</w:p></w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", body)
    result = ocr.extract_text(buf.getvalue(), ocr.DOCX_MIME)
    assert result.text == "Fees & expenses"


def test_extract_docx_rejects_non_zip():
    with pytest.raises(RuntimeError):
        ocr.extract_text(b"not a zip file", ocr.DOCX_MIME)


def test_extract_docx_rejects_zip_without_document_body():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/other.xml", "<x/>")
    with pytest.raises(RuntimeError):
        ocr.extract_text(buf.getvalue(), ocr.DOCX_MIME)


# ---------------------------------------------------------------------------
# Tesseract language routing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hint,expected",
    [
        ("en", "eng"),
        (None, "eng"),
        ("", "eng"),
        ("hi", "eng+hin"),
        ("bn", "eng+ben"),
        ("ta", "eng+tam"),
        ("xx", "eng"),
    ],
)
def test_tesseract_lang_routing(hint, expected):
    assert ocr._tesseract_lang_for(hint) == expected


# ---------------------------------------------------------------------------
# Image OCR (host-dependent)
# ---------------------------------------------------------------------------


_HAS_TESSERACT = shutil.which("tesseract") is not None


@pytest.mark.skipif(not _HAS_TESSERACT, reason="tesseract binary not installed")
def test_extract_png_reads_rendered_text():
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (900, 200), "white")
    ImageDraw.Draw(img).text((20, 60), "MINIMUM WAGE IS NOT GUARANTEED", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    result = ocr.extract_text(buf.getvalue(), "image/png", source_language="en")
    # Tesseract on a synthetic bitmap font is imperfect; assert on a stable token.
    assert "GUARANTEED" in result.text.upper()
