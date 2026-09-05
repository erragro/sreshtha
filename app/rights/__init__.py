"""Rights Guide — read-only API over ``fact_cards``.

Ships the delivery surface for the curated statute-cited content in the
``fact_cards`` table. Read-only for workers: authoring lands via
migrations (see ``alembic/versions/009_rights_guide_content.py``) and,
in v2, an admin surface.

Legal-safety constraints on the content itself live in
``docs/RIGHTS_GUIDE_CONTENT_GUIDELINES.md``; this package enforces the
delivery-side constraints:

- Only ``is_active = true`` rows are returned.
- Language falls back to English if the requested language is not yet
  active (translation-review gate; see the multilingual protocol in the
  guidelines doc).
- No user-scoped data. Same content for every authenticated worker.
"""
