"""Text extraction for uploaded contract files.

Handles five upload types:

  * ``application/pdf``  — read the born-digital text layer first (PyMuPDF);
    fall back to rasterise-then-OCR for scanned/image-only PDFs.
  * ``image/png`` / ``image/jpeg``  — OCR the image.
  * ``text/plain``  — decode the bytes.
  * ``.docx`` (``application/vnd.openxmlformats-officedocument.wordprocessingml.document``)
    — pull the run text out of ``word/document.xml``.

OCR engine
----------
Tesseract (via ``pytesseract``), not a neural engine. The system package
plus the Indic language data (``eng hin ben tam tel kan mar``) ship in the
Docker image, so there is no model download on first use and nothing to
keep resident in memory. Tesseract is a C++ engine and behaves identically
on x86 and ARM — the previous EasyOCR/torch stack produced garbled output
on the ARM64 build.

Worker documents still never leave our infrastructure: extraction is local,
per-scan cost is zero.

Language routing
----------------
Callers pass a source-language hint from the upload form. Tesseract takes a
``+``-joined language string; we always include ``eng`` so Latin script
(numbers, section headers, English clauses in bilingual contracts) is
recognised, and add the matching Indic model when the worker named one.
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from dataclasses import dataclass
from html import unescape
from typing import Optional

from PIL import Image


logger = logging.getLogger(__name__)


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OCRResult:
    text: str
    language: Optional[str]  # BCP-47 short code, mirrors the source hint
    is_low_quality: bool     # True when extracted text is suspiciously short


# ---------------------------------------------------------------------------
# Language routing
# ---------------------------------------------------------------------------

# BCP-47 short code → Tesseract's traineddata name.
_TESSERACT_LANG: dict[str, str] = {
    "en": "eng",
    "hi": "hin",
    "bn": "ben",
    "ta": "tam",
    "te": "tel",
    "kn": "kan",
    "mr": "mar",
}


def _tesseract_lang_for(source_hint: Optional[str]) -> str:
    """Which Tesseract language string to use for a given source hint.

    ``eng`` alone when the worker said the contract is English (or gave no
    usable hint of an Indic script — most platform agreements are English).
    ``eng+<indic>`` when they named a specific Indic language, so a
    bilingual contract still reads on both scripts.
    """
    hint = (source_hint or "").lower().strip()
    indic = _TESSERACT_LANG.get(hint)
    if indic and indic != "eng":
        return f"eng+{indic}"
    return "eng"


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

_MAX_PDF_PAGES = 20
_MAX_RASTER_PIXELS = 20_000_000
# Cap the decompressed size of a .docx body. A 10 MB upload could otherwise
# inflate to gigabytes ("zip bomb"); a real contract's document.xml is well
# under 5 MB.
_MAX_DOCX_XML_BYTES = 40 * 1024 * 1024

# Below this many characters we flag is_low_quality — the source is blank,
# garbled, or the worker uploaded the wrong file.
_LOW_QUALITY_THRESHOLD = 80


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


def _extract_pdf_text_layer(pdf_bytes: bytes) -> str:
    """Read a born-digital PDF's text layer before falling back to OCR.

    Most platform agreements are exported PDFs, not scans. Reading the text
    layer is faster and avoids recognition errors; scanned or image-only
    PDFs fall through to the Tesseract path.
    """
    import fitz  # noqa: WPS433 — PyMuPDF, imported lazily

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if len(doc) > _MAX_PDF_PAGES:
            raise ValueError(
                f"PDF has {len(doc)} pages; the maximum is {_MAX_PDF_PAGES}"
            )
        return "\n\n".join(page.get_text("text").strip() for page in doc).strip()
    finally:
        doc.close()


def _pdf_to_images(pdf_bytes: bytes, *, dpi: int = 300) -> list[Image.Image]:
    """Rasterise every page of a PDF to a PIL image. 300 dpi gives Tesseract
    enough resolution to read 10pt body text cleanly."""
    import fitz  # noqa: WPS433 — PyMuPDF, imported lazily

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if len(doc) > _MAX_PDF_PAGES:
            raise ValueError(
                f"PDF has {len(doc)} pages; the maximum is {_MAX_PDF_PAGES}"
            )
        pages: list[Image.Image] = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            if pix.width * pix.height > _MAX_RASTER_PIXELS:
                raise ValueError(
                    "PDF page is too large to read safely; upload a lower-resolution copy"
                )
            pages.append(
                Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            )
        return pages
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Image
# ---------------------------------------------------------------------------


def _load_image(image_bytes: bytes) -> Image.Image:
    """Decode an image blob. Converts to RGB up front so palettised PNGs and
    single-channel greyscales normalise cleanly."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.width * img.height > _MAX_RASTER_PIXELS:
        raise ValueError(
            "image is too large to read safely; upload a lower-resolution copy"
        )
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


# ---------------------------------------------------------------------------
# Tesseract
# ---------------------------------------------------------------------------


def _ocr_images(pages: list[Image.Image], *, lang: str) -> str:
    """Run Tesseract over each page image and join with blank-line page
    separators (mirrors the PDF text-layer join so Stage 1 sees the same
    structure)."""
    import pytesseract  # noqa: WPS433 — deferred; keeps module import cheap

    out: list[str] = []
    for page_no, img in enumerate(pages, start=1):
        try:
            text = pytesseract.image_to_string(img, lang=lang)
        except pytesseract.TesseractNotFoundError as exc:  # pragma: no cover
            raise RuntimeError(
                "the OCR engine (tesseract) is not installed on this host"
            ) from exc
        except pytesseract.TesseractError as exc:
            # A missing traineddata file is the common case ("Failed loading
            # language 'xxx'"). Retry on English alone rather than fail the
            # whole document.
            logger.warning("OCR: tesseract error on page %d (%s); retrying eng", page_no, exc)
            try:
                text = pytesseract.image_to_string(img, lang="eng")
            except Exception:
                logger.exception("OCR: page %d failed", page_no)
                text = ""
        if text.strip():
            out.append(text.strip())
    return "\n\n".join(out).strip()


# ---------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------


def _decode_text(file_bytes: bytes) -> str:
    """Decode an uploaded .txt file. Tries the encodings a worker's device
    or a platform export realistically produces before giving up."""
    for encoding in ("utf-8-sig", "utf-16", "utf-8", "cp1252", "latin-1"):
        try:
            return file_bytes.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return file_bytes.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# .docx
# ---------------------------------------------------------------------------

_DOCX_BREAK_RE = re.compile(r"<w:(?:br|cr)\b[^>]*/>")
_DOCX_TAB_RE = re.compile(r"<w:tab\b[^>]*/>")
_DOCX_PARA_SPLIT_RE = re.compile(r"</w:p\s*>")
_DOCX_RUN_TEXT_RE = re.compile(r"<w:t\b[^>]*>(.*?)</w:t>", re.DOTALL)


def _extract_docx_text(file_bytes: bytes) -> str:
    """Pull the visible text out of a .docx without a full XML parse.

    A .docx is a zip; the body is ``word/document.xml``. We normalise the
    handful of structural tags we care about (paragraph end, line break,
    tab) into whitespace, then lift the run text out of ``<w:t>`` elements
    with a regex. No XML entity resolution happens, so a hostile document
    can't trigger entity-expansion ("billion laughs") attacks, and the
    decompressed read is bounded.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(file_bytes))
    except zipfile.BadZipFile as exc:
        raise RuntimeError("not a valid Word document") from exc

    with archive:
        if "word/document.xml" not in archive.namelist():
            raise RuntimeError("not a valid Word document (no document body)")
        with archive.open("word/document.xml") as handle:
            raw = handle.read(_MAX_DOCX_XML_BYTES + 1)
    if len(raw) > _MAX_DOCX_XML_BYTES:
        raise RuntimeError("the Word document body is too large to read")

    xml = raw.decode("utf-8", errors="replace")
    xml = _DOCX_BREAK_RE.sub("<w:t>\n</w:t>", xml)
    xml = _DOCX_TAB_RE.sub("<w:t>\t</w:t>", xml)

    lines: list[str] = []
    for para in _DOCX_PARA_SPLIT_RE.split(xml):
        runs = _DOCX_RUN_TEXT_RE.findall(para)
        if not runs:
            continue
        line = "".join(unescape(run) for run in runs).strip()
        lines.append(line)
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_text(
    file_bytes: bytes,
    mime_type: str,
    *,
    source_language: Optional[str] = None,
) -> OCRResult:
    """Extract the text from a contract file.

    ``source_language`` is a BCP-47 code from the upload form ('hi', 'bn',
    'ta', 'te', 'kn', 'mr', 'en') or None. It only affects the OCR path —
    text formats (txt, docx, born-digital PDF) carry their own encoding.
    """
    mime_type = (mime_type or "").lower()

    # --- text formats: no OCR needed ---
    if mime_type == "text/plain":
        text = _decode_text(file_bytes).strip()
        return OCRResult(
            text=text,
            language=source_language or "en",
            is_low_quality=len(text) < _LOW_QUALITY_THRESHOLD,
        )

    if mime_type == DOCX_MIME:
        try:
            text = _extract_docx_text(file_bytes).strip()
        except Exception as exc:
            logger.exception("OCR: failed to read .docx")
            raise RuntimeError(f"could not read Word document: {exc}") from exc
        return OCRResult(
            text=text,
            language=source_language or "en",
            is_low_quality=len(text) < _LOW_QUALITY_THRESHOLD,
        )

    # --- PDF: text layer first, then OCR ---
    if mime_type == "application/pdf":
        try:
            text_layer = _extract_pdf_text_layer(file_bytes)
            if len(text_layer) >= _LOW_QUALITY_THRESHOLD:
                return OCRResult(
                    text=text_layer,
                    language=source_language or "en",
                    is_low_quality=False,
                )
            pages = _pdf_to_images(file_bytes)
        except Exception as exc:
            logger.exception("OCR: failed to read PDF")
            raise RuntimeError(f"could not read PDF: {exc}") from exc
    else:
        # image/png, image/jpeg — the service layer already whitelisted MIME.
        pages = [_load_image(file_bytes)]

    if not pages:
        return OCRResult(text="", language=source_language, is_low_quality=True)

    lang = _tesseract_lang_for(source_language)
    text = _ocr_images(pages, lang=lang)
    return OCRResult(
        text=text,
        language=source_language or "en",
        is_low_quality=len(text) < _LOW_QUALITY_THRESHOLD,
    )
