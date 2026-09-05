"""Ingest the seed statute corpus into the ``embeddings`` table.

Reads every ``.md`` file under ``data/statute_corpus/``, parses the
front-matter, chunks the body via the section-aware chunker, embeds
each chunk via ``text-embedding-3-large`` at 1024 dims, and inserts
one row per chunk into ``embeddings`` with ``source_type='statute'``.

Idempotent: a ``--reset`` flag deletes every existing
``source_type='statute'`` row for the shared tenant before re-ingesting.
Without ``--reset`` the script deletes only the rows for each
``source_id`` it is about to re-ingest — so you can add one file
without touching the others.

Usage:

    # Re-ingest the whole corpus from scratch:
    python -m scripts.ingest_statute_corpus --reset

    # Re-ingest just the files that changed (per-source_id cleanup):
    python -m scripts.ingest_statute_corpus

    # Ingest a specific file only:
    python -m scripts.ingest_statute_corpus data/statute_corpus/posh_act_2013.md
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Iterable

from sqlalchemy import text as _sql

from app.db import SessionLocal
from app.retrieval.chunker import Chunk, chunk_statute_markdown
from app.retrieval.embedder import DEFAULT_DIMENSIONS, DEFAULT_MODEL, embed


CORPUS_DIR = Path(__file__).resolve().parent.parent / "data" / "statute_corpus"


def load_files(paths: Iterable[Path]) -> list[tuple[Path, str, dict, list[Chunk]]]:
    """Read each file, extract source_id from front matter, chunk."""
    results = []
    for p in paths:
        raw = p.read_text()
        # Peek at the front matter to grab source_id + display metadata.
        # The chunker also parses front matter — we call it too so the
        # returned tuple carries the doc-level metadata for reporting.
        from app.retrieval.chunker import parse_front_matter
        doc_metadata, _ = parse_front_matter(raw)
        source_id = doc_metadata.get("source_id")
        if not source_id:
            print(f"⚠  {p.name} has no source_id in front matter — skipping")
            continue
        chunks = chunk_statute_markdown(raw, source_id=source_id)
        results.append((p, source_id, doc_metadata, chunks))
    return results


def _delete_source(db, source_id: str) -> int:
    return db.execute(_sql("""
        DELETE FROM embeddings
         WHERE source_type = 'statute'
           AND source_id = :sid
           AND tenant_id IS NULL
    """), {"sid": source_id}).rowcount


def _reset_all(db) -> int:
    return db.execute(_sql("""
        DELETE FROM embeddings
         WHERE source_type = 'statute'
           AND tenant_id IS NULL
    """)).rowcount


def _insert(db, rows: list[dict]) -> None:
    """Bulk insert with pgvector's ``vector`` cast for the embedding
    column. Batches of ~500 keep transaction size sensible without
    blowing statement size limits."""
    if not rows:
        return
    batch = 500
    for i in range(0, len(rows), batch):
        slab = rows[i : i + batch]
        # We build a parameter dict for each row. The vector column
        # needs an explicit CAST(:vec AS vector) — pgvector accepts a
        # literal string like "[0.1,0.2,...]".
        for r in slab:
            db.execute(_sql("""
                INSERT INTO embeddings
                    (source_type, source_id, source_metadata, chunk_text, embedding)
                VALUES
                    ('statute', :sid, CAST(:meta AS jsonb), :chunk,
                     CAST(:vec AS vector))
            """), {
                "sid":   r["source_id"],
                "meta":  json.dumps(r["metadata"]),
                "chunk": r["chunk_text"],
                "vec":   r["vec_literal"],
            })
        db.commit()


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="scripts.ingest_statute_corpus",
        description="Chunk + embed + insert the seed statute corpus.",
    )
    ap.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Specific files to ingest. If omitted, ingest every .md in data/statute_corpus/.",
    )
    ap.add_argument(
        "--reset",
        action="store_true",
        help="Delete every existing statute row before ingesting.",
    )
    args = ap.parse_args()

    paths = args.files or sorted(CORPUS_DIR.glob("*.md"))
    if not paths:
        print(f"No .md files found in {CORPUS_DIR}")
        sys.exit(1)

    print(f"Ingesting {len(paths)} file(s) from {CORPUS_DIR}")
    print(f"Embedding model: {DEFAULT_MODEL} @ {DEFAULT_DIMENSIONS} dims\n")

    loaded = load_files(paths)
    total_chunks = sum(len(chunks) for _, _, _, chunks in loaded)
    print(f"Loaded {total_chunks} chunks across {len(loaded)} files")
    for _, source_id, _, chunks in loaded:
        print(f"  · {source_id:50s} {len(chunks)} chunks")

    with SessionLocal() as db:
        if args.reset:
            n = _reset_all(db)
            db.commit()
            print(f"\n[reset] deleted {n} existing statute rows")
        else:
            for _, source_id, _, _ in loaded:
                n = _delete_source(db, source_id)
                if n:
                    print(f"[cleanup] deleted {n} existing rows for {source_id}")
            db.commit()

        # Embed everything in one batch (128-per-batch inside embedder).
        all_texts = [c.text for _, _, _, chunks in loaded for c in chunks]
        print(f"\nEmbedding {len(all_texts)} chunks…")
        t0 = time.time()
        vectors = embed(all_texts)
        elapsed = time.time() - t0
        print(f"  embed complete in {elapsed:.1f}s "
              f"(~{len(all_texts) / max(elapsed, 0.001):.1f} chunks/s)")

        # Assemble rows for insertion.
        rows: list[dict] = []
        vec_iter = iter(vectors)
        for path, source_id, doc_metadata, chunks in loaded:
            for chunk in chunks:
                vec = next(vec_iter)
                vec_literal = "[" + ",".join(f"{x:.7f}" for x in vec) + "]"
                # Merge doc-level metadata with chunk-specific.
                merged = dict(doc_metadata)
                merged.update(chunk.metadata)
                rows.append({
                    "source_id": source_id,
                    "metadata": merged,
                    "chunk_text": chunk.text,
                    "vec_literal": vec_literal,
                })

        print(f"\nInserting {len(rows)} rows…")
        _insert(db, rows)

    print("\nDone.")


if __name__ == "__main__":
    main()
