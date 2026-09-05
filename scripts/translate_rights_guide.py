"""Translate seeded English Rights Guide cards into HI, BN, TA via Sarvam Mayura.

Reads every ``fact_cards`` row with ``language = 'en'`` and produces a
Hindi, Bengali, and Tamil variant. Writes the result back into
``fact_cards`` at ``is_active = true`` so translations render
immediately in the app.

Legal-safety compliance (from docs/RIGHTS_GUIDE_CONTENT_GUIDELINES.md):

- The idiom library sandwich (``app/translate/idioms.py``) wraps every
  Mayura call so known idioms swap to opaque tokens and splice back
  with hand-curated equivalents.
- Citations are NEVER translated — statute names, section numbers, URLs,
  and phone numbers stay verbatim per Rule 8. The citation field is
  copied through unchanged.
- Every action step preserves its ``url`` verbatim.

Idempotent: re-running deletes and reinserts the (topic_key, lang, NULL)
row for each target language, so repeated runs pick up any edits to the
English canonical cards.

Usage:
    python -m scripts.translate_rights_guide            # default: hi, bn, ta
    python -m scripts.translate_rights_guide hi         # single language
    python -m scripts.translate_rights_guide hi bn ta   # explicit list

Native-speaker review is still recommended before treating any
translation as production-final. The migration + this script get us to
"rendering" — final content sign-off is a separate step.
"""
from __future__ import annotations

import json
import sys
import time
from typing import Iterable

from sqlalchemy import text as _sql

from app.contracts.translate import _translate_single
from app.db import SessionLocal


DEFAULT_TARGET_LANGUAGES = ("hi", "bn", "ta")


def _select_english_cards(db) -> list[dict]:
    rows = db.execute(_sql("""
        SELECT topic_key, title, summary, citation, action_steps, icon, sort_order
          FROM fact_cards
         WHERE language = 'en'
           AND tenant_id IS NULL
           AND is_active = true
         ORDER BY sort_order, topic_key
    """)).mappings().all()
    return [dict(r) for r in rows]


def _translate_long(text: str, target: str, max_chars: int = 900) -> str:
    """Translate text that may exceed Mayura's 1000-char per-call cap.

    Splits on paragraph boundaries (double newline) so each chunk is
    linguistically coherent, translates chunk by chunk, and rejoins with
    the original paragraph separators.
    """
    if not text.strip():
        return ""
    if len(text) <= max_chars:
        return _translate_single(text, target)

    paragraphs = text.split("\n\n")
    out: list[str] = []
    buffer = ""
    for p in paragraphs:
        candidate = f"{buffer}\n\n{p}" if buffer else p
        if len(candidate) <= max_chars:
            buffer = candidate
        else:
            if buffer:
                out.append(_translate_single(buffer, target))
                buffer = ""
            # If the paragraph itself is too big, split it at sentence
            # boundaries (period+space) as a last resort.
            if len(p) > max_chars:
                sents, cur = [], ""
                for s in p.split(". "):
                    tail = ". " if s != p.split(". ")[-1] else ""
                    piece = f"{s}{tail}"
                    if len(cur) + len(piece) <= max_chars:
                        cur += piece
                    else:
                        if cur:
                            sents.append(_translate_single(cur, target))
                        cur = piece
                if cur:
                    sents.append(_translate_single(cur, target))
                out.append(" ".join(sents))
            else:
                buffer = p
    if buffer:
        out.append(_translate_single(buffer, target))
    return "\n\n".join(out)


def _translate_action_steps(steps: list[dict], target: str) -> list[dict]:
    """Translate label + description on each step, keep url verbatim."""
    out: list[dict] = []
    for step in steps or []:
        translated_label = _translate_single(step["label"], target)
        translated_desc = _translate_single(step["description"], target)
        entry = {
            "label": translated_label,
            "description": translated_desc,
        }
        if step.get("url"):
            entry["url"] = step["url"]  # verbatim
        out.append(entry)
    return out


def _upsert_translated_card(db, *, topic_key: str, language: str, title: str,
                            summary: str, citation: str | None,
                            action_steps: list[dict], icon: str | None,
                            sort_order: int) -> None:
    # Delete-then-insert to sidestep Postgres NULL-tenant matching in ON CONFLICT.
    db.execute(_sql("""
        DELETE FROM fact_cards
        WHERE topic_key = :topic_key
          AND language = :language
          AND tenant_id IS NULL
    """), {"topic_key": topic_key, "language": language})

    db.execute(_sql("""
        INSERT INTO fact_cards
            (topic_key, language, title, summary, citation, action_steps,
             icon, sort_order, is_active)
        VALUES
            (:topic_key, :language, :title, :summary, :citation,
             CAST(:action_steps AS jsonb), :icon, :sort_order, true)
    """), {
        "topic_key": topic_key,
        "language": language,
        "title": title,
        "summary": summary,
        # Citation is NEVER translated. Rule 8.
        "citation": citation,
        "action_steps": json.dumps(action_steps),
        "icon": icon,
        "sort_order": sort_order,
    })


def translate_all(targets: Iterable[str] = DEFAULT_TARGET_LANGUAGES) -> None:
    targets = tuple(targets)
    with SessionLocal() as db:
        cards = _select_english_cards(db)
        if not cards:
            print("No English cards found. Run alembic upgrade first.")
            return

        print(f"Found {len(cards)} English card(s). Targeting {targets}.\n")

        for card in cards:
            print(f"→ {card['topic_key']}")
            for lang in targets:
                start = time.time()
                # Title + summary through Mayura; idiom library wraps each call.
                translated_title = _translate_single(card["title"], lang)
                translated_summary = _translate_long(card["summary"], lang)
                translated_steps = _translate_action_steps(
                    card["action_steps"] or [], lang,
                )

                _upsert_translated_card(
                    db,
                    topic_key=card["topic_key"],
                    language=lang,
                    title=translated_title,
                    summary=translated_summary,
                    citation=card["citation"],  # verbatim
                    action_steps=translated_steps,
                    icon=card["icon"],
                    sort_order=card["sort_order"],
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
