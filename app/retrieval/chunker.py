"""Section-boundary-aware chunker for legal source text.

The default text splitter used in RAG tutorials (recursive character
splitting at fixed sizes with overlap) is a poor fit for statutes: a
section can be 50 characters or 5000 characters, and splitting at
arbitrary character positions destroys the referential context — the
section number reference — that makes a chunk useful for citation.

This chunker walks the source text respecting these boundaries:

1. Explicit section markers — ``Section N``, ``Section N(a)``, ``§N``,
   ``Article N``, and their sub-clause variants.
2. Chapter markers — ``Chapter I``, ``Chapter II``.
3. When a section is too long to fit in one chunk (default ~1500
   chars), it splits at paragraph boundaries with a rolling window,
   annotating each sub-chunk with the parent section number so the
   retrieved metadata still carries the citation.

Input is markdown with a YAML-style front matter block. The front
matter carries the document-level metadata (statute name, year, URL);
each chunk inherits it and adds section-specific metadata.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


# Chunk size in characters. Roughly 400 tokens per 1500 chars for
# English legal text with standard whitespace. Chosen so top-5
# retrieval per Stage 2 batch stays under gpt-4o's context comfortably.
DEFAULT_MAX_CHARS = 1500
DEFAULT_MIN_CHARS = 200  # never emit a chunk smaller than this on its own

# Ordered by strength — the first regex that matches wins the split.
_SECTION_HEAD_RE = re.compile(
    r"^\s*(?:(?:#{1,6}\s+)?"
    r"(Section|Sec\.?|Article|Art\.?|§|Chapter|Part|Rule)\s+"
    r"([IVXLC]+|[0-9]+[A-Za-z]?(?:\([a-z0-9]+\))*)"
    r".*)$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Chunk:
    text: str
    source_id: str
    source_type: str            # "statute" | "fact_card" | ...
    metadata: dict[str, Any]    # includes chunk-specific fields (section_number, chunk_index)


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Extract YAML-style front matter (delimited by ``---``) and the
    body. Returns (metadata, body). If no front matter, returns ({}, text)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    meta_block, body = m.group(1), m.group(2)
    metadata: dict[str, Any] = {}
    for line in meta_block.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata, body


def chunk_statute_markdown(
    text: str,
    *,
    source_id: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    min_chars: int = DEFAULT_MIN_CHARS,
) -> list[Chunk]:
    """Chunk a statute markdown file into embeddable pieces.

    Priority order for boundaries:
    1. Section / Article / Chapter headers.
    2. Paragraph breaks (blank lines) within an over-long section.
    3. Sentence breaks if a single paragraph still exceeds max_chars.
    """
    doc_metadata, body = parse_front_matter(text)
    body = body.strip()
    if not body:
        return []

    # Split into (header, body) segments by scanning for section heads.
    segments: list[tuple[str | None, str, str | None]] = []
    # elements = (section_head_line_or_None, content, section_number_or_None)
    last_pos = 0
    matches = list(_SECTION_HEAD_RE.finditer(body))
    if not matches:
        segments.append((None, body, None))
    else:
        # Any content before the first header
        pre = body[: matches[0].start()].strip()
        if pre:
            segments.append((None, pre, None))
        for i, m in enumerate(matches):
            head_line = m.group(0).strip()
            section_number = m.group(2).strip() if m.group(2) else None
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            content = body[start:end].strip()
            segments.append((head_line, content, section_number))

    chunks: list[Chunk] = []
    chunk_index = 0
    for head_line, content, section_number in segments:
        # Build the chunk text: prepend the header for referential context.
        full = (head_line + "\n" + content).strip() if head_line else content
        for piece in _split_long(full, max_chars=max_chars, min_chars=min_chars):
            metadata = dict(doc_metadata)
            metadata["chunk_index"] = chunk_index
            if section_number:
                metadata["section_number"] = section_number
            chunks.append(Chunk(
                text=piece.strip(),
                source_id=source_id,
                source_type="statute",
                metadata=metadata,
            ))
            chunk_index += 1
    return chunks


def _split_long(text: str, *, max_chars: int, min_chars: int) -> list[str]:
    """Split ``text`` into pieces <= max_chars, splitting at paragraph
    boundaries when possible. Small over-limit texts are returned as a
    single chunk to avoid producing tiny fragments."""
    if len(text) <= max_chars:
        return [text]

    # Paragraph split
    paragraphs = re.split(r"\n\s*\n", text)
    if len(paragraphs) == 1:
        # Single paragraph too long — sentence-split
        return _sentence_split(text, max_chars=max_chars)

    out: list[str] = []
    buffer = ""
    for para in paragraphs:
        candidate = (buffer + "\n\n" + para) if buffer else para
        if len(candidate) <= max_chars:
            buffer = candidate
        else:
            if buffer and len(buffer) >= min_chars:
                out.append(buffer)
                buffer = ""
            if len(para) > max_chars:
                # Recurse
                out.extend(_sentence_split(para, max_chars=max_chars))
                buffer = ""
            else:
                buffer = para
    if buffer:
        out.append(buffer)
    return out


def _sentence_split(text: str, *, max_chars: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    buf = ""
    for s in sentences:
        candidate = (buf + " " + s) if buf else s
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            if buf:
                out.append(buf)
            buf = s
    if buf:
        out.append(buf)
    return out
