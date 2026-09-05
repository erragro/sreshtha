"""Translate Schemes Finder content (name, description, apply_note)
into HI, BN, TA via Sarvam Mayura.

Reads every ``scheme_translations`` row with ``language='en'`` and
produces a Hindi, Bengali, and Tamil variant per scheme. Writes back
to ``scheme_translations`` as new rows (unique per scheme_id +
language).

Legal-safety compliance:
- Scheme names include acronyms and proper nouns (PM Suraksha Bima
  Yojana, e-Shram, PMJAY, Ayushman Bharat). Mayura preserves these
  reasonably well; the idiom library still wraps every call.
- ``apply_url`` and ``estimated_time`` live on the ``schemes`` row and
  are language-agnostic. This script does not touch them.

Usage:
    python -m scripts.translate_schemes            # hi, bn, ta
    python -m scripts.translate_schemes hi
"""
from __future__ import annotations

import sys
import time
from typing import Iterable

from sqlalchemy import text as _sql

# Reuse the same helper used for Rights Guide so paragraph chunking
# behaviour stays consistent across modules.
from scripts.translate_rights_guide import _translate_long
from app.contracts.translate import _translate_single
from app.db import SessionLocal


DEFAULT_TARGET_LANGUAGES = ("hi", "bn", "ta")


def _select_english_scheme_rows(db) -> list[dict]:
    rows = db.execute(_sql("""
        SELECT st.id AS translation_id,
               st.scheme_id,
               s.key AS scheme_key,
               st.name,
               st.description,
               st.apply_note
          FROM scheme_translations st
          JOIN schemes s ON s.id = st.scheme_id
         WHERE st.language = 'en'
           AND s.is_active = true
           AND s.tenant_id IS NULL
         ORDER BY s.sort_order, s.key
    """)).mappings().all()
    return [dict(r) for r in rows]


def _upsert_scheme_translation(db, *, scheme_id, language, name, description,
                               apply_note):
    db.execute(_sql("""
        DELETE FROM scheme_translations
         WHERE scheme_id = :scheme_id AND language = :language
    """), {"scheme_id": scheme_id, "language": language})

    db.execute(_sql("""
        INSERT INTO scheme_translations
            (scheme_id, language, name, description, apply_note)
        VALUES
            (:scheme_id, :language, :name, :description, :apply_note)
    """), {
        "scheme_id": scheme_id,
        "language": language,
        "name": name,
        "description": description,
        "apply_note": apply_note,
    })


def translate_all(targets: Iterable[str] = DEFAULT_TARGET_LANGUAGES) -> None:
    targets = tuple(targets)
    with SessionLocal() as db:
        rows = _select_english_scheme_rows(db)
        if not rows:
            print("No English scheme translations found. Run alembic upgrade first.")
            return

        print(f"Found {len(rows)} English scheme(s). Targeting {targets}.\n")
        for row in rows:
            print(f"→ {row['scheme_key']}")
            for lang in targets:
                start = time.time()
                translated_name = _translate_single(row["name"], lang)
                translated_desc = _translate_long(row["description"], lang)
                translated_note = (
                    _translate_long(row["apply_note"], lang)
                    if row["apply_note"] else None
                )
                _upsert_scheme_translation(
                    db,
                    scheme_id=row["scheme_id"],
                    language=lang,
                    name=translated_name,
                    description=translated_desc,
                    apply_note=translated_note,
                )
                db.commit()
                elapsed = time.time() - start
                print(f"    {lang}  ok  ({elapsed:.1f}s)")

        print("\nDone. Native-speaker review is still recommended before")
        print("treating these as production-final content.")


if __name__ == "__main__":
    args = sys.argv[1:]
    targets = tuple(args) if args else DEFAULT_TARGET_LANGUAGES
    translate_all(targets)
