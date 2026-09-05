# Rights Guide — Content Guidelines

**Purpose:** enforce legal safety in every fact card, in every language,
in every version. These rules bind content authors, translators, and
the UI layer.

**Bind to:** every row in the `fact_cards` table, and every string a
worker sees inside the Rights Guide module.

**Non-negotiable — a card that violates any of these must not ship.**

---

## Rule 1 — State the law. Do not advise.

**Do:**
- "Under Section 113 of the Code on Social Security 2020, platform-based
  workers are a recognised category eligible for welfare schemes."
- "e-Shram registration is free."
- "The Karnataka Platform-Based Gig Workers (Social Security and
  Welfare) Ordinance, 2024 established a state welfare board."

**Don't:**
- "You should sue the platform."
- "You are entitled to ₹50,000 compensation."
- "This clause is illegal and you can ignore it."
- "Demand a written contract."

Every sentence about worker action must be a description of a documented
procedure (register on this portal, call this helpline), never a
strategic recommendation.

## Rule 2 — Every claim carries a citation.

- Statutes: name + section number + link to Gazette if available.
- Schemes: scheme name + issuing authority + official portal URL.
- Reports: report title + publisher + year (for context claims like
  "most gig workers earn under ₹15,000/month").

If a claim has no citation, remove the claim.

## Rule 3 — No case law. Ever.

Case law is fact-specific and shifts on appeal. Sreshtha does not have
the legal review capacity to safely cite it. Cite only:
- Central Acts and Codes
- State Acts, Ordinances, Rules
- Government scheme documents
- Published reports from named institutions (NITI Aayog, Fairwork
  India, Ministry of Labour reports)

## Rule 4 — Action steps are procedural, never strategic.

Every action step must be:
- A portal link ("Register on eshram.gov.in")
- A helpline call ("Call India Labourline: 1800-419-1550")
- A named authority contact ("Contact the Karnataka Gig Workers Welfare
  Board")
- A concrete step ("Keep a copy of your uploaded contract")

Never:
- "Demand this from the platform"
- "Ask for higher compensation"
- "Refuse to sign until they change X"

## Rule 5 — No rate, fee, or benefit amount claims in the card body.

Benefit amounts change. Cess percentages change. A stale claim in an
educational card is a liability. If a scheme has a benefit amount, link
to the official portal so the worker sees the current figure. The card
tells them the scheme exists and where to find it, not what it pays.

Exceptions where numbers may appear:
- The India Labourline phone number (1800-419-1550).
- Statute + section numbers.
- Publication years of cited reports.
- The `Not legal advice` disclaimer (contains no dollar figures).

## Rule 6 — India Labourline is the standing escalation.

Every card ends with a Labourline callout. Consistent phone number,
consistent framing. Language-appropriate translation of the surrounding
text is fine; the number stays as digits.

## Rule 7 — "Not legal advice" disclaimer, everywhere.

Displayed:
- At the top of the Rights Guide list page.
- At the bottom of every fact card detail page.
- Announced by screen readers.

Standard text (English canonical):

> This page shares publicly documented information about your rights
> under Indian law. It is not legal advice. For formal help, call India
> Labourline at 1800-419-1550.

Translated for each supported language. The Labourline number stays as
digits.

## Rule 8 — No individual eligibility claims.

**Do:** "This scheme is intended for workers registered under e-Shram."
**Don't:** "You qualify for this scheme."

The card describes who the scheme is designed for. Determining whether
any specific worker qualifies is the government portal's job.

---

## Translation protocol

Cards are authored in English (canonical). Translations to Hindi,
Bengali, and Tamil are produced via Sarvam Mayura, then reviewed by a
native speaker before publication.

**What Mayura translates:**
- Card title
- Summary paragraphs
- Action step labels and descriptions

**What stays untranslated (verbatim):**
- Statute names ("Code on Social Security 2020", "Karnataka
  Platform-Based Gig Workers Ordinance 2024")
- Scheme names ("e-Shram", "PM Suraksha Bima Yojana", "Ayushman Bharat")
- Authority names ("India Labourline", "Ministry of Labour and
  Employment", "IRDAI")
- URLs
- Phone numbers (rendered as digits, not spelled out)
- Section references ("Section 113", not "धारा 113")

The idiom library (from Contract Reader) applies to Rights Guide
translation as well — any English legal idiom in the corpus is
tokenised before Mayura sees it and spliced back after.

## Change protocol

Any change to a card's summary or citation:
1. Update the English canonical.
2. Re-run Mayura translation for HI, BN, TA.
3. Flag the card as `pending_review` until a native speaker approves
   each translation.
4. Only cards with all four language variants at `active` status
   render in the list.

Card drafts, edits, and translations are versioned in migrations
(`alembic/versions/NNN_rights_guide_*.py`), not edited in the database
by hand.

## Content review checklist (per card, per language)

Before a card is marked `active`:

- [ ] Every factual claim has an inline citation.
- [ ] No action step reads as advice.
- [ ] No rate, fee, or benefit amount appears in the body.
- [ ] Citation URL resolves.
- [ ] Statute name and section number are correct.
- [ ] India Labourline callout is present.
- [ ] "Not legal advice" disclaimer will render on the detail page.
- [ ] Translation preserves statute names, scheme names, URLs, phone
      numbers verbatim.
- [ ] Native speaker has reviewed and approved the translation.

If any box is unchecked, the card is `draft` or `pending_review`,
never `active`.
