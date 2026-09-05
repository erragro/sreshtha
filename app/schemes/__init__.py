"""Schemes Finder — 3-question wizard over the ``schemes`` +
``scheme_translations`` tables.

Delivery-side rules (mirroring ``app/rights``):

- Only ``is_active = true`` schemes are returned.
- Language falls back to English if the requested language has no
  ``scheme_translations`` row for a scheme.
- Matching runs in Python against ``schemes.eligibility_rules`` (JSONB)
  so admins can edit rules in v2 without touching code.
- No individual eligibility claims. The matcher returns "candidate
  schemes for a worker profile"; the official portal is where actual
  eligibility gets decided.
"""
