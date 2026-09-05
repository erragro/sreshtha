# Sreshtha — Product Requirements Document

**Version:** 0.2 (funder-review draft)
**Owner:** Surajit Chaudhuri (founder)
**Last updated:** 2026-09-05
**Primary audience:** impact funders (foundations, CSR desks), grant committees, and state welfare-board procurement leads. Secondary: hackathon / accelerator reviewers.
**Companion documents:** [MONETIZATION.md](MONETIZATION.md) (revenue model, unit economics), [STATUS_2026-08-23.md](STATUS_2026-08-23.md) (build snapshot), [DESIGN.md](DESIGN.md) (pipeline internals), [RIGHTS_GUIDE_CONTENT_GUIDELINES.md](RIGHTS_GUIDE_CONTENT_GUIDELINES.md) (fact-card safety rules).

---

## 0. What changed since v0.1

v0.1 (2026-08-13) was written as a hackathon submission plan. It made three claims that later drifted from reality and that a funder's diligence would flag:

| v0.1 claim | v0.2 correction |
|---|---|
| OCR via Gemini Vision | In-house **EasyOCR** (open-source, on-prem, zero per-scan cost) since the 2026-08-15 architecture pivot. Worker documents never leave our infrastructure. |
| "Sold to gig platforms and aggregators under compliance framings" as a core channel | Aggregator revenue is a **late, carefully-bounded channel (months 18–36)**, never a funder of the advocacy features. Primary funding: philanthropic grants → state welfare-board contracts → insurance/fintech distribution. See §8 and [MONETIZATION.md](MONETIZATION.md). |
| "Retrieval-first" chatbot with a 0.75 similarity "safety cage" | RAG is a **roadmap item, not a shipped safety control**. v1's safety guarantee is the deterministic output validator (§7.4), which runs on every response regardless of retrieval. The "cage" language has been removed. |
| Gemini owns all reasoning + generation across every language | **Per-stage hybrid.** Stage 1 (extract) uses OpenAI `gpt-4o-mini` with Structured Outputs enforcement + gpt-4o fallback on low confidence — cheap, schema-guaranteed, fast. Stage 2 (annotate) uses OpenAI `gpt-4o` with RAG over a curated statute corpus (pgvector, HNSW, `text-embedding-3-large` @ 1024 dims via Matryoshka). Stage 3 (rewrite) uses Vertex AI Gemini 2.5 Flash with Mayura-style chunked parallelism for warmer pre-translation tone. Sarvam Mayura still owns Indic translation. Vertex Gemini remains an explicit provider swap via `LLM_PROVIDER=vertex` for the whole reasoning stack. Rationale in §7.2, per-stage detail in §7.3. |
| Seven Indic languages ship in the Contract Reader v1 | **v1 Contract Reader output ships Hindi + Bengali + English only.** The worker-facing app shell also launches in those reviewed locales, with one persisted worker-language preference. Tamil / Telugu / Kannada / Marathi re-enable for Contract Reader once (a) idiom-library coverage per language reaches ≥100 entries, and (b) native-speaker review completes on the Rights Guide fact cards in those languages. The 7-language shape is preserved in the schema and in Rights Guide / Schemes / Complaint Helper — the constraint is Contract Reader-specific. |
| Chatbot output safety was described as prompt engineering + retrieval | **Deterministic output validator with a no-shot rule library.** Response generation for Stage 3 (contract clauses) and the chatbot both flow through a `clause_rules` table of hand-authored per-pattern rule specs. A fast classifier maps each output to a taxonomy slug (or "novel"). Matched patterns are rendered under strict per-rule constraints; novel outputs still pass through a universal validator (tone lint, blocklist, required-content, statute-match). Any violation triggers one retry with corrections, then a safe canonical fallback. See §7.4. Migration + seed corpus of 15–20 clause patterns is the next content-heavy build. |

Other v0.2 additions: a real **Legal & Regulatory Posture** section (§6), a **Validation & Evidence** section (§9), an **Impact Measurement** framework (§10), **team de-risking** (§11), and an explicit **funding ask + use of funds** (§13).

---

## 1. Executive summary

**Sreshtha** (श्रेष्ठ / শ্রেষ্ঠ / சிரேஷ்ட — "the best") is a mobile-first web platform that helps Indian gig workers understand the contracts they signed, know the rights they hold, discover the government schemes they already qualify for, and file complaints that reach a real authority — in their own language, at literacy levels the market ignores.

**Why this, why now.** India has ~7.7 crore gig workers today, projected to ~23.5 crore by 2030 (NITI Aayog, 2022). The Code on Social Security 2020 recognised gig workers as a distinct category and mandated welfare infrastructure; Karnataka and Rajasthan have operationalised state welfare boards funded by a cess on platform transactions. The legal scaffolding now exists. **What is missing is the worker-facing surface that turns statute into "here is what to do this afternoon."** No consolidated worker-facing product occupies this space; the closest analogue, Fairwork India, is a research and advocacy vehicle, not a product.

**What we've built.** One shell, five modules, common conversational surface:

1. **Contract Reader** *(shipped, production-quality)* — upload the contract you signed; get it explained clause-by-clause in your language, with the clauses that deserve attention flagged.
2. **Rights Guide** *(shipped)* — 5 curated, citation-backed fact cards on minimum wage, injury, grievance escalation, e-Shram registration, and contract fairness. English canonical + Hindi, Bengali, Tamil translations via Sarvam Mayura (native-speaker review is the publication gate for translations; script and translation UI live either way).
3. **Chatbot (Sahaayak)** *(shell live; domain retargeting in progress)* — natural-language Q&A over the Rights Guide and the worker's own documents.
4. **Schemes Finder** *(shipped)* — a three-question wizard surfacing every central and state scheme a worker qualifies for. 10 schemes indexed with structured eligibility rules; Hindi, Bengali, Tamil descriptions live via Mayura translation.
5. **Complaint Helper** *(data model + 5 seeded templates + escalation-ladder routing built; API + UI pending)* — draft a formal complaint in the worker's language, routed to the right authority.

Contract Reader is the anchor. As of 2026-09-04 it runs a **per-stage hybrid reasoning pipeline**: OpenAI `gpt-4o-mini` for schema-guaranteed clause extraction (Stage 1), OpenAI `gpt-4o` for statute-annotated risk labelling with RAG over a curated statute corpus (Stage 2, in flight), and Vertex AI Gemini 2.5 Flash for the warm worker-facing rewrite (Stage 3, chunked parallel). Sarvam Mayura then translates the finished English into the worker's language with a curated idiom library and four tone registers. The pipeline exceeds the original v1 scope and is the artefact that carries the demo.

**The mission-aligned business model.** Workers never pay for contract analysis, rights content, or complaint drafting. The platform is funded by parties who are already paying to reach or serve this workforce: philanthropic and CSR grants first, then state welfare-board integration contracts, then regulated insurance and fintech distribution. Aggregator money, if taken at all, comes late and never touches complaint routing. Full model and unit economics in [MONETIZATION.md](MONETIZATION.md).

**The moat.** Not any single feature. It is the compounding **curated Indic-language corpus** — idiom library, tone registers, reviewed fact cards, complaint templates — that general-purpose translation cannot replicate because it cannot self-correct on gig-worker-specific language it does not know it is mis-rendering. Distribution is a partnership problem, not a customer-acquisition-cost problem: welfare boards and unions need this surface and bring their own worker bases.

---

## 2. Problem statement

### 2.1 The workforce

- **~7.7 crore gig workers in India today** (NITI Aayog, 2022); **~23.5 crore projected by 2030** — 6.7% of the non-agricultural workforce.
- **Language**: Hindi ~40%, Telugu ~7%, Marathi ~7%, Bengali ~8%, Tamil ~6%, Kannada ~4%, other Indic ~28%, English-first <1%.
- **Bengali migrant concentration** in Delhi NCR, Bengaluru, Mumbai, Chennai, Pune, Hyderabad — construction, delivery, sanitation, domestic work.
- **Median age** 27 (Ola Mobility Institute); **female participation** 6–8% (BetterPlace 2024); **rural origin** 68% (NCAER 2023).

### 2.2 The harm

Documented in Fairwork India (IIIT-B / Oxford), IFAT surveys, Ola Mobility Institute, and NITI Aayog:

- **40% earn under ₹15,000/month** before vehicle costs, fuel, and platform charges.
- **90% have no savings**; **78%** report a household income shock in any given quarter.
- **83% of cab drivers work >10 hours/day**; **50%+ of delivery riders** report heat exhaustion.
- **Wage theft is widespread** — deducted incentives, disputed cancellations, opaque per-order maths.
- **92% sign the platform agreement without reading it** (IFAT 2023); **88% of those** signed a version they cannot re-download.
- **61% don't know they can complain to a labour officer**; **78% don't know the e-Shram grievance cell exists**.

### 2.3 The regulatory framework — new, and unused

- **Code on Social Security 2020**, ss. 113–114 — first central law recognising gig workers; scheme design and registration mandated; rules notified 2024.
- **e-Shram portal** — 30+ crore unorganised workers registered by mid-2024; only ~4% of gig workers report knowing what benefits attach.
- **Karnataka Platform-Based Gig Workers (Social Security and Welfare) Ordinance 2025** — first state welfare board; 1–2% cess on transactions.
- **Rajasthan Platform-Based Gig Workers (Registration and Welfare) Act 2023** — welfare board established.
- **Central Motor Vehicles Rules amendment (2024)** — aggregator responsibility for driver safety training and insurance.
- **Consumer Court + Labour Court dual pathway** for wage disputes — almost nobody knows both channels exist.

**The gap:** workers do not know these mechanisms exist, do not know how to activate them, and have no one translating the letter of the law into a concrete next step.

### 2.4 What exists today, and why it does not close the gap

| Tool | What it does | Why it falls short |
|---|---|---|
| e-Shram portal | Registration + UAN | Registration only; benefits downstream and unclear; English/Hindi, desktop-first |
| Namma Yatri | Alt ride-booking (Bengaluru autos) | One city, one modality; no rights or legal layer |
| Kaam.com / Apna | Job discovery | Nothing about the terms you are signing |
| Union WhatsApp groups | Peer support, protest coordination | Human-moderated; no scale, persistence, or language coverage beyond the leader's language |
| Fairwork India | Annual platform grading | Advocacy instrument for policymakers, not a worker tool |
| State welfare-board portals | Scheme registration | Opaque eligibility; scheme discovery near-impossible |

No consolidated worker-facing product exists.

---

## 3. Target users

### 3.1 Primary — Rahul, delivery rider, Bengaluru

24, from Balrampur (UP), 18 months in the city. Hindi native, some Bhojpuri, functional English for app UX. Swiggy + Zomato + Rapido, 11-hour days, ₹18–22k/month before petrol. Signed contracts he cannot recall. Owes a friend ₹8,000 from a delivery-fall medical bill. Wants to know if the platform owes him for the days off, and to complain if it does. Phone: 3-year-old Redmi, 3G, WhatsApp + Reels heavy, uses Google voice search.

*Today:* asks the union WhatsApp group, gets vague mixed-language answers, gives up.
*With Sreshtha:* uploads a screenshot of his contract, hears the injury clauses explained in Hindi, reads a fact card on injury compensation, lands on a pre-filled complaint for the Karnataka welfare board.

### 3.2 Secondary — Sabina, domestic worker, Bengaluru

38, from Murshidabad (WB), migrated 6 years ago. Bengali native, functional Hindi, no English. Urban Company + one private household. Never seen a written contract. Wants to know whether she is on the e-Shram register and what happens if she is injured.

*Today:* nothing; assumes nothing exists.
*With Sreshtha:* voice-first Bengali onboarding; a walk-through of her entitlements under the Karnataka Ordinance; help filing the missing registrations.

### 3.3 Tertiary — Muthu, driver, Chennai

32, Tamil native, Ola + occasional truck runs. Reads Tamil, some English. Wants a straight answer on whether the platform's ₹1 lakh insurance covers last month's vehicle damage.

*With Sreshtha:* uploads the denial letter, hears the reason in Tamil, sees the ombudsman escalation path with a pre-filled complaint.

### 3.4 Institutional stakeholders (not v1 users; they fund and distribute)

- **State welfare boards** — have a cess-funded mandate and no worker-facing surface. Sreshtha's Rights Guide + Schemes Finder + Complaint Helper *are* that surface.
- **Unions** (IFAT, All India Gig Workers Union, state affiliates) — have members, want year-round digital services to justify dues. White-label deployment.
- **Foundations / CSR desks** (Omidyar Network India, Rohini Nilekani Philanthropies, Azim Premji Foundation, Ford, Tata Trusts) — fund exactly this intersection of marginalised-workforce, public-digital-good, AI-for-good.
- **Regulated insurers / responsibly-priced lenders** — distribution partners once a worker base exists, under the §6 and [MONETIZATION.md](MONETIZATION.md) §2 bright lines.

**Aggregators are not on this list as a primary funder.** A platform will not pay to license a tool that flags its onboarding clauses and arms its workforce with grievance letters, and Sreshtha will not weaken those features to make itself sellable to one. Any future aggregator relationship is a late, transparent CSR partnership where workers retain independent access and complaint routing is untouched (see [MONETIZATION.md](MONETIZATION.md) §3.4).

---

## 4. Product vision & principles

### 4.1 Vision

**Every gig worker in India should be able to understand their contract, know their rights, and file a complaint that goes somewhere — in their own language, from their own phone, in one sitting.**

### 4.2 Principles (ranked)

1. **Language-first.** Hindi and Bengali are full worker-facing launch locales. Tamil is a platform-priority locale and is released module by module only after its content-quality gate passes. English is a transparent fallback, not the norm.
2. **Voice-assisted, icon-led, text-supported.** Reading is the last resort. ASR/TTS on meaningful interactions *where network allows*; text always works. (v1 submission ships without voice — see §12.)
3. **Deterministic where it matters, generative where it helps.** Scheme eligibility, complaint routing, statute references, template filling — Python. LLMs handle language understanding and tone. **No LLM-drafted legal conclusions.**
4. **Cite everything.** Every claim shows its source (statute + section, or scheme document). Every chatbot answer shows what it drew on.
5. **Operational language, not legal verdicts.** Contract clauses are flagged by *what they do to the worker operationally* ("gives the platform sole discretion to deactivate"), never by a legal judgment ("this clause is illegal"). See §6.
6. **Trust signals throughout.** Government logos when linking to official portals. Explicit "this is information, not legal advice" framing. India Labourline (1800-419-1550) always one tap away.
7. **Offline-capable content.** Rights Guide and uploaded contracts remain readable when the network dies. Complaint drafts sync on reconnect.
8. **Lite-mode default.** Assumes 3G / 2G. Aggressive image and audio compression. Progressive enhancement.
9. **No password fields — with recovery that survives a SIM change.** OTP or biometric to sign in; **a recovery PIN set at onboarding, plus optional email, plus one-tap "download my vault"** so a migrant worker who changes numbers does not lose their documents. See §7.5.
10. **Worker-owned data.** Uploaded contracts and drafts belong to the worker. Deletion is one tap. DPDP Act 2023 posture in §6.4.
11. **Warm, human tone.** No corporate register. No "we regret to inform you." No em dashes. Every string in every language passes the same tone lint.

### 4.3 Language surface, content availability, and fallback

Sreshtha treats these as separate settings; conflating them creates mixed-language, unsafe experiences.

- **Worker locale** controls every fixed worker-facing interface string: onboarding, navigation, upload instructions, consent, processing status, risk labels, errors, safety notices, Labourline prompts, download controls, and accessibility labels. It is selected at onboarding, can be changed in settings, and is persisted across modules. The reviewed v1 locales are Hindi, Bengali, and English.
- **Document source language** is declared or detected at upload. It guides OCR and clause extraction only; it never changes the app interface language.
- **Module output language** defaults to the worker locale but is constrained by the module's reviewed-content availability. Contract Reader v1 permits Hindi, Bengali, and English. Rights Guide and Schemes Finder may expose Tamil only when the relevant translated content has passed native-speaker review.
- **Fallback is explicit.** When a requested translation is unavailable or still in review, the interface says that the original English content is being shown; it never silently mixes languages or labels English as translated content.
- **Fixed UI copy is not machine-translated at runtime.** It lives in versioned message catalogs and is reviewed by a native speaker before release. Backend failures are surfaced as stable error codes that the client maps to reviewed locale strings, rather than exposing raw English server messages.

---

## 5. Solution overview

One shell, five modules, one account, one chatbot.

### 5.1 The shell (built, from the QuickBites substrate, rebranded)

- **Auth** — email + password today; **OTP-first with recovery** before public launch.
- **Sessions** — chat sessions with title, history, rename, delete.
- **Module registry** — modules registered by super-admin, gated per user and per tenant.
- **Tenant infrastructure** — `tenants` + `tenant_memberships` tables (migration 012) with a scripted onboarding path (`scripts/bootstrap_tenant.py`). Every content row already carries a nullable `tenant_id` (null = shared library); welfare boards and unions can be provisioned as first-class tenants with their own admin owner in one command.
- **Tenant configuration** — business units, issue types, response templates, admin-editable ("Conversation Studio").
- **Chat pipeline** — Cardinal-inspired synchronous phases with a deterministic rule-enforcement stage.
- **LLM abstraction** — `LLMProvider` protocol with `chat(role, system, user, schema=…)` and `chat_stream()` methods. Two concrete providers: `OpenAIProvider` (chat completions via HTTPS, engages Structured Outputs when a JSON schema is passed) and `VertexAIProvider` (google-genai SDK, `response_schema` for structured mode). Selection at call site via `get_provider(language, provider="openai" | "vertex")`, or globally via the `LLM_PROVIDER` env selector (default `openai`; `vertex` is the explicit swap for the entire reasoning stack). AI Studio bare-key access was removed after Google blocked the key path.
- **Admin panel** — user + access matrix, module + tone-spec editing.

### 5.2 The five modules

| # | Module | v1 scope (public launch) | Status (2026-09-04) |
|---|---|---|---|
| 1 | **Contract Reader** | Upload PDF/image ≤10MB → EasyOCR → per-stage hybrid reasoning (OpenAI mini extract → OpenAI + RAG annotate → Vertex Gemini rewrite, chunked parallel) → Mayura translation with idiom library + tone register; 3 pre-loaded sample contracts; "ask about this clause" hook | **Shipped.** Exceeds original scope. Language surface for v1 tightened to Hindi + Bengali + English per the §0 correction; other Indic languages preserved in schema and re-enable post-launch. |
| 2 | **Rights Guide** | Curated statute-cited fact cards; each card = plain-language summary + citation + procedural action steps + Labourline escalation; publication guarded by an 8-rule content-safety spec ([RIGHTS_GUIDE_CONTENT_GUIDELINES.md](RIGHTS_GUIDE_CONTENT_GUIDELINES.md)) | **Shipped v0.1.** 5 fact cards seeded (minimum wage, injury on the job, grievance escalation, e-Shram registration, contract fairness). English canonical `is_active=true`; Hindi + Bengali + Tamil rendered via Mayura + idiom library (`scripts/translate_rights_guide.py`), publication-gated on native-speaker review per card × language. UI falls back to English when a language is in review. Expansion to 15 cards is a content-authoring track, not a code track. |
| 3 | **Chatbot (Sahaayak)** | Retargeted Cardinal pipeline; retrieval over Rights Guide + user documents *(roadmap)*; LLM answer with a not-verified disclaimer + deterministic output validator (§7.4) + no-shot rule library on every response; language auto-detect | Shell live; domain retargeting (prompts, Stage-2 rules, persona, disclaimer, no-shot rules) in progress; RAG scoped to Stage 2 first, chatbot RAG follows. |
| 4 | **Schemes Finder** | 3-question wizard (state / occupation / demographics) → matched schemes with eligibility rules JSON, documents, apply-link | **Shipped.** 10 schemes indexed and matched via Python (`app/schemes/service.py`) against a `WorkerProfile` — no LLM in the match path. Includes e-Shram, PMSBY, PMJJBY, PMJAY, PMSYM, APY, SSY, PDS, Karnataka welfare fund, Rajasthan welfare board. English canonical + HI/BN/TA descriptions via Mayura (`scripts/translate_schemes.py`). |
| 5 | **Complaint Helper** | Topic picker → template fill (voice/text) → worker-language + English output → routed to the right authority; copy / WhatsApp share / PDF | Data model + migration + 5 seeded templates (wage theft, injury, dismissal, harassment, insurance) with escalation-ladder routing built (migration 011). Service layer, API, and frontend pending. |

### 5.3 Honest status summary

**Three of the five modules are shipped or shipped-with-a-content-gate.** Contract Reader (anchor, production-quality); Rights Guide (5 fact cards live, English canonical, translations gated on native-speaker review); Schemes Finder (10 schemes with the Python matcher live). Chatbot Sahaayak needs domain retargeting, not building. Complaint Helper needs the service + UI on top of a built data model. Voice (Sarvam ASR/TTS), Stage-2 RAG over the statute corpus, the `clause_rules` no-shot guide, OTP-with-recovery, offline service worker, and Cloud Run deploy under the Sreshtha brand are pending — all funded, none launch-blocking for a controlled first pilot. A funder should read the product as "anchor proven, platform scaffolded, three of five modules live, content and distribution are the work ahead" — which is exactly what grant capital funds.

---

## 6. Legal & regulatory posture

This is the section a funder's diligence will probe hardest. Treating it as a disclaimer footer (as v0.1 did) is not sufficient.

### 6.1 What Sreshtha is, and is not

**Sreshtha is a legal-information and document-comprehension tool.** It explains what a contract says, what a statute provides, and which authority hears which complaint. It surfaces publicly available government information in accessible language.

**Sreshtha does not practise law.** It does not represent workers, does not appear before any forum, does not give individualised legal advice on the merits of a specific dispute, and does not draft or negotiate contracts. Under the **Advocates Act 1961**, the reserved activity is representation and appearance; providing legal information and self-help document preparation is not reserved. Sreshtha stays firmly on the information side of that line and routes anything that needs a lawyer to India Labourline, state legal-aid authorities, or partner NGOs.

### 6.2 How the Contract Reader avoids becoming legal analysis

- **Operational flags, not legal verdicts.** A clause is labelled by its operational effect on the worker — `restrictive / high-attention`, `worth knowing`, `standard` — never `illegal`, `void`, `unlawful`, or `unenforceable`. The taxonomy in code is already `adverse / worth_knowing / fine`; v0.2 formalises the worker-facing labels as operational.
- **A deterministic output sanitiser** (the existing Stage-2 validator, extended for this domain) runs on every LLM-generated clause explanation. If the model emits "illegal", "you are entitled to", "you should sue", "this violates", or similar, the sanitiser rewrites to cited, hedged phrasing ("The Code on Social Security 2020, s. 113, sets out protections in this area; a labour officer can tell you how it applies to your situation") or blocks the response.
- **Every clause card links to the primary statute.** The worker is one tap from the source text, not dependent on our paraphrase.
- **No positive reliance language.** A clause is never described in a way that invites the worker to rely on it ("this protects you", "you are covered"). Favourable clauses are framed as "commonly considered a standard protection; confirm the specifics with the platform."
- **Human escalation is always present.** Every module surfaces India Labourline and, where relevant, the state legal-aid authority.

### 6.3 How the Rights Guide stays defensible

- **Every fact card is reviewed by a qualified labour-law practitioner before publication.** This is a funded commitment (retainer or pro-bono partnership), not aspirational. No card ships unreviewed.
- **Statutes and schemes only. No case law** — case-law interpretation requires ongoing lawyer review Sreshtha will not have at v1 scale.
- Cards carry a visible "last reviewed" date and the reviewer's credential class.

### 6.4 Data protection (DPDP Act 2023)

- **Consent** collected at upload, purpose-limited to processing that document for that worker.
- **Data minimisation** — no document content used for model training; no cross-worker data compilation; no sale of data even anonymised (a bright line, [MONETIZATION.md](MONETIZATION.md) §2).
- **Worker-owned** — one-tap deletion; one-tap export.
- **On-prem OCR** — EasyOCR runs on Sreshtha infrastructure, so raw contract images never transit a third-party vision API.
- Storage-at-rest encryption; access logging; a published privacy notice in all supported languages.

### 6.5 Liability containment

- **Professional indemnity / technology E&O insurance** taken out on first institutional funding.
- **Advisory board** includes a practising labour lawyer and a worker-organisation representative.
- **Terms of use** frame Sreshtha as information, disclaim reliance, and preserve the worker's right to independent counsel — in plain language, in every supported script, not buried.
- **Incident process** — a documented path for a worker (or a platform) to flag an inaccurate output; two substantiated accuracy complaints on any card trigger re-review.

---

## 7. Technical architecture

### 7.1 High level

```
Worker's phone (web)  —  React 19 + Vite + Tailwind v4 + shadcn/ui
   Hindi / Bengali / English UI (v1 Contract Reader scope)
   Voice-assist · TTS (roadmap)
        │  HTTPS + JWT
FastAPI backend
   Modules Registry · Cardinal Pipeline · Content Store · Tenant Layer
        │
   ┌────┴──────── Reasoning stack ─────────┐
   │                                       │
   Postgres (users, content,               │
   sessions, tenants,                      │
   idiom library, embeddings ← RAG)        │
                                           │
   Contract Reader per-stage hybrid:       │
     Stage 1  OpenAI gpt-4o-mini           │
              (+ 4o fallback on low conf)  │
     Stage 2  OpenAI gpt-4o                │
              + RAG over statute corpus    │
              (pgvector HNSW, text-        │
              embedding-3-large @ 1024)    │
     Stage 3  Vertex AI Gemini 2.5 Flash   │
              (chunked parallel, Mayura-   │
              style boundary tokens)       │
                                           │
   Cardinal chat pipeline (default):       │
     OpenAI (LLM_PROVIDER=vertex swap)     │
                                           │
   Sarvam Mayura v1 (all Indic translation)│
   Sarvam Transliteration (Roman↔native)   │
   EasyOCR (on-prem, per-language readers) │
   Sarvam ASR/TTS (roadmap)                │
```

The whole reasoning stack sits behind a single `LLMProvider` protocol. Each stage explicitly names its provider at the call site (`get_provider(provider="openai")` or `get_provider(provider="vertex")`), so a change of provider for any one stage is a one-line edit and never leaks into another. The `LLM_PROVIDER` env var is a global fallback selector when a call site doesn't specify.

### 7.2 Key design decisions

**Deterministic where it matters.** Scheme matching, complaint routing, statute references, and template filling are Python. LLMs do three things: language detection, clause understanding on uploaded contracts, and warm chat prose when there is no library answer. Nothing binding is generated, and the output sanitiser (§6.2) is the backstop.

**Per-stage hybrid reasoning.** (Pivot 2026-09-04 after ML research on structured-output accuracy, RAG-for-legal-domain retrieval quality, and per-provider tone quality.) Each stage in Contract Reader runs on the provider best suited to its task, all sharing one `LLMProvider` protocol:

- **Stage 1 (Extract)** — OpenAI `gpt-4o-mini` with **Structured Outputs** (`response_format=json_schema`, `strict: true`). Schema-guaranteed JSON eliminates parse failures. Structured extraction is a shape-imposition task where mini is at effective parity with 4o at ~15× lower cost (~$0.0015/contract vs ~$0.025). A confidence-gate fallback retries on gpt-4o if the model returns `confidence < 0.4` or zero clauses.
- **Stage 2 (Annotate)** — OpenAI `gpt-4o` grounded by **RAG over a curated statute corpus** (the Code on Social Security 2020, Karnataka Platform Gig Workers Ordinance 2024, Rajasthan Platform Gig Workers Act 2023, Central Motor Vehicles Rules 2024 amendment, POSH Act 2013). Retrieval index is `pgvector` HNSW over `text-embedding-3-large` embeddings reduced to 1024 dimensions via Matryoshka Representation Learning — the highest-quality legal-domain OpenAI embedding at storage cost lower than the small model. A cosine-similarity threshold of ~0.75 gates retrieval; below threshold, the annotator emits `citation: null` rather than inventing a section number.
- **Stage 3 (Rewrite)** — Vertex AI Gemini 2.5 Flash. Gemini's warmer, more idiomatic English is the better upstream for Sarvam Mayura's Indic translation than 4o's slightly more formal register. **Mayura-style chunked parallelism**: clauses are batched 5 per call and run through a `ThreadPoolExecutor` of 6, then merged. A separate small Gemini call aggregates the `overview` block (top summary + top actions) from the whole rendered set — so overview actions reference genuine top-priority red-tier clauses, not chunk-local ones.

Sarvam Mayura v1 stays dedicated to Indic translation (fact cards, complaint templates, Stage 3 output). Sarvam Transliteration powers the Roman ↔ native-script toggle. Neither runs on the chat-completions abstraction.

Gemini AI Studio bare-key access (`GEMINI_API_KEY`) was removed after Google blocked the key path — Vertex AI is the only Google reasoning path in Sreshtha now, and the `LLM_PROVIDER=vertex` swap routes every reasoning call there when explicitly set.

**No-shot rule library with a deterministic validator.** (New in v0.2.) Response generation for Stage 3 (contract clauses) and for the chatbot both terminate at a `clause_rules` table of hand-authored per-pattern rule specs — not exemplars. Each row is a rule spec for a clause pattern such as `unilateral_termination_no_notice` or `weekly_payment_after_deductions`, with:

- `generation_rules` — 100–200-word English rule spec (what MUST be said, what MUST NOT be said, when to reference which statute section)
- `forbidden_content` — blocklist phrases that trigger a rewrite
- `required_content` — anchor phrases the output must contain
- `citation` — statute name + section + URL (verified against the RAG corpus)
- `topic_hint` — Rights Guide fact-card slug for cross-linking
- `default_risk_tier`, `contract_types`, `version`, `reviewed_by`, `reviewed_at`, `is_active`, `tenant_id`

Flow: a fast classifier (gpt-4o-mini) maps the clause to a taxonomy slug or "novel". Matched patterns generate under strict rule constraints; novel patterns still generate but only under Layer 1 universal rules (tone lint, length caps, action-verb enforcement, red-clause action requirement). Every output — matched or novel — passes through the same deterministic validator (§7.4) before it reaches a worker. A failed validation triggers one retry with corrections, then a safe canonical fallback derived from the rule row.

The library is chosen over few-shot exemplars because (a) legal reasoning is naturally rule-shaped, (b) authoring one rule spec is ~5× the throughput of curating three-plus exemplars, (c) a lawyer can review 20 rule specs where they cannot review 100+ exemplar outputs, and (d) versioned rule rows carry provenance (reviewer, reviewed_at) that exemplars cannot. Migration + seed of 15–20 high-frequency gig-worker clause patterns is the next content-heavy build.

**Contract Reader output language: Hindi + Bengali + English for v1.** (New in v0.2.) Contract Reader renders worker-facing analysis in three languages only for the first release: Hindi (broadest reach), Bengali (migrant workforce across Delhi NCR, Bangalore, Mumbai per persona §3.2), and English (fallback for the reviewer and for bilingual contracts). The app chrome follows the worker locale defined in §4.3; source-contract language remains an OCR/extraction concern. Tamil, Telugu, Kannada, Marathi remain fully in the schema, in the `TargetLanguage` type, and in Rights Guide / Schemes / Complaint Helper — the constraint is Contract Reader-specific and is lifted per language when (a) the idiom library covers ≥100 entries for that language and (b) the fact-card corpus for that language completes native-speaker review. This is a quality-preserving scope tightening, not a strategic retreat.

**On-prem OCR.** EasyOCR + PyMuPDF, cached readers per language pair, English always bundled for bilingual contracts. Zero per-scan cost, no vendor dependency, worker documents stay on our infrastructure. **Known limitation:** first upload per language pair pays a ~10–15 s model-load cost (surfaced to the worker as a one-line notice); an image-preprocessing pass (deskew, adaptive threshold for phone-camera photos) is a near-term hardening item.

**Contract processing is asynchronous.** Upload returns immediately; a background task advances the document through a committed status machine (`uploaded → ocr → stage1 → stage2 → stage3 → translated → ready`), and the viewer renders each stage's output as it lands. A worker on 3G sees OCR text within seconds and a progressively hydrating explanation, not a 40-second spinner. This is why multi-stage LLM latency is a UX detail here, not a blocker.

**Translation throughput.** Stage-3 output is batched into Mayura-cap-friendly chunks with pass-through boundary tokens (`[[ROW_n]]`, `[[FLD]]`) and a three-level degradation cascade (chunk → per-field → keep English for that row). A 94-clause contract goes from ~11 minutes of sequential calls to ~30 seconds. Composes with the idiom substitute/restore sandwich. Code: [app/contracts/translate.py](../app/contracts/translate.py).

**Retrieval is a cost and quality lever, not a safety control.** When RAG ships, it will cut chatbot LLM traffic 60–80% *[estimate]* and improve citation quality. It is not what makes the chatbot safe — the deterministic output validator is, and it runs whether retrieval hits or misses. v1 launches with the validator and an honest "best understanding, not verified" disclaimer on unlibraried answers.

**Multi-tenant from day one.** Every content row carries a nullable `tenant_id` (null = shared). Welfare boards and unions get white-label configs — branding, custom fact cards, custom complaint routing — with no code changes.

### 7.3 Three-stage contract reasoning

Ported from `thought-translate` prior art, then substantially evolved for Sreshtha's per-stage hybrid architecture. Every stage has a strict output schema (enforced natively via OpenAI Structured Outputs or Vertex `response_schema` where the provider supports it) and every stage degrades rather than cascades — a partial Stage 2, for example, still lets the worker see Stage 1's verbatim clauses.

**Stage 1 — Extract (OpenAI gpt-4o-mini + Structured Outputs)**

Reads the OCR'd contract and emits:
- `contract_type` — one of `aggregator / labour / vendor / rental / unknown`
- `confidence` — float 0..1
- `metadata` block — `parties[]` (role + name), `signature_date`, `effective_date`, `term`, `jurisdiction`, `governing_language`
- `clauses[]` — verbatim clause text in the original language, stable `id`, `heading`, `section_number`

Provider: OpenAI `gpt-4o-mini`, `role="fast"`, temperature 0, max 16K output tokens. Schema is a strict JSON Schema dict enforced by the API — no parse failures possible on a well-formed API response. **Confidence-gate fallback**: if the mini call returns `confidence < 0.4` OR zero clauses OR any parse error, the same call re-runs on `role="smart"` (`gpt-4o`). Result carries `_fallback: "smart"` for A/B measurement. On a Swiggy delivery-agreement fragment the mini call classifies as `aggregator` at confidence 0.9, extracts 3 clauses, populates parties and jurisdiction, and skips the fallback path.

**Stage 2 — Annotate (OpenAI gpt-4o + RAG)**

Takes Stage 1's clauses and annotates each with:
- `risk` — `red` (adverse / high-attention), `amber` (worth knowing), `green` (favourable / boilerplate)
- `citation` — structured `{name, section, url}` (all three nullable; when set, they refer to the specific statute chunk the retriever surfaced)
- `note` — 1–2-sentence English explanation of the risk assessment
- `topic_hint` — Rights Guide fact-card slug (`minimum_wage`, `injury_on_the_job`, `grievance_escalation`, `e_shram_registration`, `contract_fairness`) when the clause maps to one, else `null`

Contract-type-aware reasoning is built into the system prompt: aggregator contracts foreground Motor Vehicles Rules 2024 amendment + welfare-board rules; labour contracts foreground Industrial Disputes Act §2A + EPFO/ESIC; vendor contracts foreground Consumer Protection Act; rental contracts foreground CMV Rules + deposit / depreciation.

**RAG plumbing** (planned): each batch of 5 clauses embeds a query concatenating clause text + heading, retrieves top-5 statute chunks by cosine similarity ≥ 0.75 from the `embeddings` table (pgvector HNSW), injects the retrieved chunks into the user message with source URLs, and instructs the annotator to cite what it retrieved (or set `citation` all-null if nothing meets threshold). A failed Stage 2 falls back to Stage-1-only output ("here is what the contract says; we could not cross-check the law today").

**Stage 3 — Rewrite (Vertex Gemini + chunked parallel)**

Produces the worker-facing English rendition, which Mayura then translates. Per clause:
- `explanation` — plain-language rewrite of the clause (2–3 sentences)
- `implication` — what the clause means for the worker in practice (1 sentence; references the citation section when helpful)
- `action` — one procedural step, or `null` (never `null` for red clauses — enforcement fills a safe default if the LLM under-emits)

Plus a top-level `overview`:
- `top_summary` — 1–2-sentence English framing of the contract as a whole
- `top_actions[]` — 1–3 highest-priority procedural actions from the red-tier clauses

**Chunked parallelism (Mayura-style):** clauses split into chunks of 5 (`_STAGE3_CHUNK_SIZE`) and run through `get_provider(provider="vertex")` in a `ThreadPoolExecutor` capped at 6 workers. Per-chunk render then a single small aggregation call generates the `overview` from the whole rendered set — so overview actions aren't chunk-local. A 30-clause contract completes Stage 3 in ~4–5 s instead of ~15 s sequential. The prompt is split into `_SYSTEM_RENDER_ONLY` (per-clause) and `_SYSTEM_OVERVIEW_ONLY` (aggregation) so each call carries only the rules it needs.

Once Stage 3 emits, Mayura translates the finished English into the worker's target language + tone register, with the idiom-library substitute/restore sandwich preserving legal-idiom fidelity through the translator call (§7.5 in [DESIGN.md](DESIGN.md)).

**Latency budget for a real 30-clause contract:** OCR ~5–10 s → Stage 1 mini ~3–6 s → Stage 2 (6 parallel gpt-4o calls) ~8–12 s → Stage 3 (6 parallel Gemini + 1 overview) ~4–5 s → Mayura chunked translation ~15–25 s. Total ~35–58 s end-to-end. The worker sees OCR text within seconds and each stage's output as it lands — this is why the multi-stage latency is a UX detail rather than a blocker.

### 7.4 The deterministic output validator + no-shot rule library

The single most important safety control. Two layers, both running on every generative output (chatbot response, Stage-3 clause explanation) before it reaches a worker.

**Layer 1 — `clause_rules` no-shot library** (planned, seeded with 15–20 highest-frequency gig-worker clause patterns)

- A fast classifier (gpt-4o-mini call, ~$0.0001/clause) maps the clause to a taxonomy slug (`unilateral_termination_no_notice`, `weekly_payment_after_deductions`, `broad_indemnification`, `non_compete_beyond_engagement`, `insurance_paid_by_worker`, `arbitration_in_distant_city`, etc.) or `novel`.
- **Matched patterns** render under the rule row's constraints — a 100–200-word English rule spec authored by a labour-law reviewer, plus explicit `forbidden_content` blocklists and `required_content` anchor phrases the output must contain. The LLM generates from the rule spec, not from an exemplar; the rule spec plus the clause text plus Stage 2's citation is the whole input.
- **Novel clauses** still generate but only under the universal validator below. Every novel clause is logged as a candidate for a new taxonomy row.
- Rules carry `version`, `reviewed_by`, `reviewed_at`, `is_active`, and a nullable `tenant_id` so welfare boards and unions can author their own overrides. Version bumps on every edit — nothing silently mutates.

**Layer 2 — Universal deterministic validator** (already partially built as Cardinal's Stage-2 rule enforcement, extending for this domain)

- **Blocklist rewrite** — legal-conclusion verbs ("illegal", "void", "you are entitled to", "you should sue", "this violates") are rewritten to cited, hedged forms or the response is regenerated.
- **Citation match** — if the output names a statute section, it must match the `citation.section` Stage 2 already assigned to that clause. Otherwise the citation is stripped and downgraded to "a labour officer can confirm this for your situation".
- **Tone lint** — the §8.4 spec, enforced in code, in every language: no em dashes, no corporate register ("kindly", "we regret", "as per"), no negative-emotion vocabulary ("frustration", "annoying", "disappointment"), max sentence caps per field.
- **Red-clause action requirement** — a clause tagged `risk: red` by Stage 2 must have a non-null `action` field. If the LLM under-emits (which it does; recent probe confirmed the fallback fills reliably), a safe canonical action is auto-filled: `"Ask the platform in writing to clarify or waive this clause and save the response."` The fill event is logged.
- **Verb-start action check** — the `action` field must begin with a verb (regex check). Non-verb starts are regenerated.
- **Length caps** — `explanation ≤ 240 chars`, `implication ≤ 160`, `action ≤ 200`.
- **Escalation injection** — if the clause topic is safety-critical (injury, assault, unpaid wages, harassment, trafficking), the India Labourline number (1800-419-1550) and the safety-complaint path are appended regardless of what the model produced.
- **Failure handling** — a validation failure triggers one retry with a correction prompt naming the failed rules. Still failing → fallback to the rule row's canonical default. If the row is novel with no default, the safe fallback is `"This clause needs manual review. Please call India Labourline: 1800-419-1550."` No garbage ships.

**A/B measurement.** Every rendered output carries a `source` tag — `"library-rule"`, `"novel-llm"`, or `"fallback"` — persisted in the Stage 3 output blob. This lets us measure library hit rate, validator retry rate, and fallback rate in production and target the next taxonomy rows at the highest-frequency `novel` clauses.

### 7.5 Identity and recovery

OTP-first sign-in, **plus** a recovery path built for a workforce that changes SIMs and shares devices:

- A **6-digit recovery PIN** set during onboarding, usable to reclaim an account from a new number.
- **Optional email** as a second recovery factor (many workers have a Gmail from Android setup even if they never use it).
- **One-tap vault export** (contracts + drafts as a zip) so a worker's documents are never hostage to a phone number.
- Shared-device safety — explicit sign-out, no "remember me" by default, session pinned to a short idle timeout on the worker-facing app.

### 7.6 Data model

**Shipped** (migrations 001–012):

| Migration | Tables / changes | Purpose |
|---|---|---|
| 001 | `users`, `chat_sessions`, `turns`, `bot_executions` | Baseline runtime |
| 002 | Auth columns on `users` (password hash, super-admin) | Auth |
| 003 | `modules`, `user_module_access` | Module registry + per-user gating |
| 004 | Conversation Studio: `business_units`, `data_points`, `issue_types`, `ack_templates` | Chat taxonomy admin |
| 005 | `fact_cards`, `schemes` + `scheme_translations`, `complaint_templates`, `uploaded_contracts` (target language, stages JSONB); modules reseeded for Sreshtha | Content substrate for the five modules |
| 006 | `uploaded_contracts.target_language`, `uploaded_contracts.target_script` | Worker's language + script choice on upload |
| 007 | `idiom_library`, `idiom_translations` | Aho-Corasick-scanned pre-Mayura substitution library |
| 008 | `uploaded_contracts.translation_mode` | Tone register (formal / modern-colloquial / classic-colloquial / code-mixed) |
| 009 | 5 Rights Guide fact cards seeded canonical English | Rights Guide v0.1 content |
| 010 | 10 Schemes Finder scheme rows + English `scheme_translations` seeded | Schemes Finder v0.1 content |
| 011 | 5 Complaint Helper templates + escalation-ladder routing seeded | Complaint Helper content substrate |
| 012 | `tenants`, `tenant_memberships`; `users.default_tenant_id`; `uploaded_contracts.tenant_id`; FK constraints on all content tables' `tenant_id` columns | Multi-tenant infrastructure for partner deployments |

Every content table (`fact_cards`, `schemes`, `complaint_templates`, `idiom_library`) carries a nullable `tenant_id` FK → `tenants(id)` with `ON DELETE SET NULL` — so a tenant's overrides revert to the shared library rather than disappearing when the tenant is archived.

**Planned** (in flight):

| Migration | Tables / changes | Purpose |
|---|---|---|
| 013 | Enable pgvector extension; create `embeddings` table (`source_type`, `source_id`, `chunk_text`, `vector(1024)`, HNSW index, `tenant_id`) | Stage 2 RAG over statute corpus + future chatbot RAG over Rights Guide |
| 014 | `clause_rules` — no-shot rule library (slug, name, contract_types, default_risk_tier, generation_rules, forbidden_content, required_content, citation, topic_hint, version, reviewed_by, reviewed_at, is_active, tenant_id) | Stage 3 no-shot response generation with per-pattern rule specs |
| 015 (later) | `stage3_source` column on `uploaded_contracts.stages` JSONB path; production A/B logging table for rule hits vs fallbacks | Measurement of library coverage + validator retry rate |
| 016 (later) | Voice: `tts_cache` + Sarvam-ASR request log | Voice-first surface |

The corpus for migration 013's initial seed is the Code on Social Security 2020, Karnataka Platform Gig Workers Ordinance 2024, Rajasthan Platform Gig Workers Act 2023, Central Motor Vehicles Rules 2024 amendment, and POSH Act 2013 — five statutes, chunked into roughly 1,000 vectors, embedded via `text-embedding-3-large` at 1024 dims for a one-time cost of ~$0.07. HNSW index footprint at that corpus size is under 40 MB per Postgres deployment.

---

## 8. Business model (summary — full detail in MONETIZATION.md)

**Workers stay free forever on everything that is the point of the app** (contract analysis, rights content, complaint drafting). Funding comes from parties already paying to reach or serve this workforce, unlocked in order:

| # | Channel | Timing | Notes |
|---|---|---|---|
| 1 | Foundation + CSR grants | Months 0–12 | Seed capital. Non-dilutive. ₹2.5–3.5 cr target Phase 1. |
| 2 | State welfare-board integration contracts | Months 6–24 | The channel that scales. Boards have cess money and no worker surface. ~₹300–800/registered worker/year *[estimate]*. |
| 3 | Regulated insurance + fintech distribution | Months 12–30 | Only IRDAI/RBI-licensed, responsibly-priced partners. 15–30% first-year premium commission (standard). |
| 4 | Aggregator CSR ("improve our Fairwork rating") | Months 18–36 | Bounded; transparent; workers keep independent access; complaint routing untouched. |
| 5 | Union white-label + member subscriptions | Months 9–30 | Distribution partner as much as customer; each deal brings a member base. |
| 6 | Direct-to-worker paid tiers (pay-per-use, credits, Pro ₹99/mo) | Month 12+ | Humane caps; safety-critical drafts always free and uncapped; the app that never took from workers when they most needed it gets to take a little when they can give. |

**The chatbot cost trap is designed for, not ignored.** Every worker turn is a metered Gemini + Mayura call; at 5M users an uncontained chatbot is a ₹230 cr/year line. Containment: retrieval-first architecture + a soft 10-LLM-turn/month free-tier cap (retrieval answers unlimited) + curated sponsored placements from an allowlist (never on the Contract Reader, never inside a complaint body). Under this combination the chatbot stays under ₹15/user/month even at 5M users. Full analysis: [MONETIZATION.md](MONETIZATION.md) §6–§7.

**Unit economics at maturity:** ~₹40–90/user/year fully-loaded cost; ₹150–400/user/year blended revenue; 60–80% contribution margin, driven by welfare boards and unions doing distribution for free. *[All directional; validate per counterparty before quoting.]*

---

## 9. Validation & evidence

v0.1 had no evidence section. A funder needs to see the validation that has happened and the plan for what has not.

### 9.1 What supports the thesis today

- **Secondary research** — the §2 statistics are from NITI Aayog, Fairwork India, IFAT, Ola Mobility Institute, NCAER. The harm and the awareness gap are well-documented.
- **Regulatory signal** — three state governments have legislated welfare boards that structurally require a worker-facing surface. The demand for §8 channel 2 is created by law, not by us.
- **Absence of a competitor** — no consolidated worker-facing product exists; the gap is real, not already-served.
- **Build signal** — the anchor module shipped to production quality in ~8 working days, with translation-quality depth (idiom library, tone registers) beyond the original spec. This is evidence of execution capacity.
- **Blog + narrative** — published at [erragro.github.io/sreshtha-blog](https://erragro.github.io/sreshtha-blog/).

### 9.2 What has NOT been validated yet (and the plan)

| Open question | How we will answer it | When |
|---|---|---|
| Will workers actually upload a contract to an app they just found? | 15–20 moderated sessions with delivery riders and domestic workers in Bengaluru (Hindi + Bengali), via an NGO partner; measure task completion and comprehension | First 60 days post-funding |
| Is the Hindi/Bengali/Tamil output actually readable to a functionally-literate worker? | Comprehension testing on 5 fact cards and 3 contract explanations per language; back-translation review; the labour-lawyer review from §6.3 | First 90 days |
| Does a drafted complaint reach a human and get a response? | Track 50 real drafted complaints through the 7/14-day follow-up; measure response rate (target: 15% within 14 days) | Months 3–6 |
| Will a welfare board sign? | Warm intro to the Karnataka board via Fairwork India's IIIT-B group; MoU then paid pilot | Months 3–9 (govt cycles are 9–18 months) |
| Will a foundation fund it? | 3–5 grant conversations off the demo + blog; Omidyar / Rohini Nilekani / one international funder | Months 0–6 (grant cycles are 3–6 months) |

**No user counts, pilot commitments, or funder conversations are claimed here because none are yet real.** They will be added as they become real.

---

## 10. Impact measurement

### 10.1 Theory of change

**Inputs** (curated multilingual content, reasoning pipeline, distribution partnerships) → **Outputs** (workers who read a contract clause they understand, find a scheme they qualify for, draft a complaint that is routed correctly) → **Outcomes** (workers who take an action they would not otherwise have taken: register for a scheme, escalate a wage dispute, decline or renegotiate a contract term) → **Impact** (measurable recovery of entitlements — scheme enrolments, complaint responses, disputed amounts recovered — and a documented evidence base on gig-contract terms that informs policy).

### 10.2 Metrics

**Reach & engagement (first 90 days post-launch):**
- 1,000 first-time workers *[target]*.
- 40% complete at least one non-chat action (upload / read a card / find a scheme / draft a complaint).
- 20% return in the second week.
- Language mix roughly 40% Hindi / 15% Bengali / 15% Tamil / 30% other Indic + English.

**Outcome metrics (first 6 months):**
- **Scheme enrolments initiated** — count of workers who click through to an official apply-link from Schemes Finder.
- **Complaint response rate** — 15% of drafted complaints receive a response within 14 days (measured by the follow-up prompt).
- **Comprehension** — ≥80% of moderated-session participants correctly answer a comprehension check on a fact card or clause explanation in their language.
- **NPS 40+** (bar: platform CX averages ~20).

**Impact / evidence base (ongoing):**
- Anonymised, aggregate corpus of contract clauses analysed — the most common restrictive clauses across platforms, published (with consent, aggregate only) as a policy contribution, complementary to Fairwork India's grading.

### 10.3 Measurement method

Product analytics for reach/engagement; the built-in 7/14-day complaint follow-up for response rate; quarterly moderated sessions for comprehension; a privacy-reviewed aggregation job for the clause corpus. All outcome reporting distinguishes *initiated* from *completed* (Sreshtha surfaces eligibility and drafts complaints; the state processes claims and the authority acts).

---

## 11. Team & execution risk

**Current team: one founder** (Surajit Chaudhuri — product + full-stack engineering). This is the single biggest execution risk and v0.2 states it plainly.

**De-risking plan, in order:**

1. **First funding hire: a policy / government-relations lead** — welfare-board contracts (§8 channel 2) are a relationship-and-procurement game the founder is not positioned to run solo.
2. **Labour-lawyer engagement** (retainer or pro-bono partnership) — required for §6.3 fact-card review before any card ships.
3. **NGO field partner** — for the moderated validation sessions (§9.2) and worker distribution.
4. **Second engineer** — once the content and pilot workload exceeds one person, targeted at RAG, voice, and the offline layer.

**What the solo track record shows:** an existing production shell (auth, sessions, multi-tenant config, admin, LLM abstraction) retargeted and a genuinely finished anchor module in ~8 working days, including translation-infrastructure depth beyond spec. The founder can build; the ask funds the team that turns a built product into a distributed one.

**Advisory board (to form on funding):** a practising labour lawyer, a gig-worker-union representative, someone with state-government procurement experience, and a Fairwork India / IIIT-B researcher.

---

## 12. Roadmap

### 12.1 Near term — public-launch readiness (next ~6 weeks)

**Content**

- Rights Guide: expand from 5 → 15 fact cards. Author English canonical, Mayura-translate, then native-speaker-review per (card × language). English cards live already; Hindi + Bengali + Tamil translations rendered, publication-gated on review.
- Schemes Finder: 10 schemes already indexed with English + HI/BN/TA descriptions live. Post-launch: expand to 15 (add Sukanya Samriddhi-adjacent + state-specific).
- Complaint Helper: build the service layer + API + frontend on top of the built data model (5 templates × 4 languages already seeded via migration 011).

**Contract Reader — the per-stage hybrid landing**

- Per-stage `get_provider(provider=…)` dispatch, Stage 1 → gpt-4o-mini + Structured Outputs, Stage 3 → Vertex Gemini + chunked parallel: **all shipped as of 2026-09-04.**
- Stage 2 RAG plumbing (migration 013): pgvector, `embeddings` table with HNSW `vector(1024)` index, statute-corpus ingestion script, retrieval helper.
- Statute corpus seed: 5 statutes (CoSS 2020, Karnataka Ordinance 2024, Rajasthan Act 2023, CMV Rules 2024 amendment, POSH 2013) via `text-embedding-3-large` at 1024 dims.
- Stage 2 refactor: RAG-grounded gpt-4o annotations with the ≥0.75 cosine similarity gate on citation emission.
- `clause_rules` no-shot rule library (migration 014): 15–20 seeded rule specs for the highest-frequency gig-worker clause patterns, per-row versioning and reviewer attribution.
- Stage 3 refactor: fast classifier → library-rule render or LLM-with-rule → validator → safe fallback. `stage3_source` A/B tagging on every rendered clause.

**Platform**

- Chatbot Sahaayak: domain retargeting (prompts, Stage-2 rules, Sahaayak persona, disclaimer plumbing). Same deterministic output validator + `clause_rules`-adjacent rule library.
- OTP-first auth + recovery PIN + vault export (§7.5).
- Internationalisation: build one persisted worker-locale system and reviewed UI message catalogs for HI + BN + EN across every worker-facing route; map stable backend error codes to those catalogs. Keep Contract Reader output to HI + BN + EN; re-enable TA/TE/KN/MR per language when idiom-library coverage + fact-card native review complete for that language.
- Cloud Run deploy under Sreshtha branding; load-tested.
- Frontend: Contract Reader mobile-first refactor. Detail page renders the new `metadata`, structured `citation`, `topic_hint` cross-link to Rights Guide, and top-level `overview` block. Upload page bottom-sheet language/tone selectors.

**Deferred to post-launch:** voice (Sarvam ASR/TTS), chatbot RAG over Rights Guide, offline service worker, contract image-preprocessing (deskew + adaptive threshold for phone-camera photos), a browser-extension "read this before you sign" surface, and non-English languages beyond HI/BN in Contract Reader. None are launch-blocking; all are in the funded plan.

### 12.2 Phase 1 (months 0–12) — grants + one welfare board

Grant stack closed (₹2.5–3.5 cr non-dilutive). Karnataka welfare-board MoU → paid pilot. IFAT distribution partnership. First policy hire, lawyer engagement, NGO field partner. Moderated validation complete. Team 3–5.

### 12.3 Phase 2 (months 13–24) — multi-state + insurance rev-share

Rajasthan / Tamil Nadu / Telangana board contracts. 300k–500k active workers. One insurance partnership live. RAG + voice shipped. Team 15–25.

### 12.4 Phase 3 (month 25+) — financial products + freemium

Insurance + fintech mix drives ₹15–25 cr. Direct-worker paid tiers at scale. 2–3 aggregator CSR partnerships under the §6 bright lines. Sreshtha becomes the default worker-side app for the segment.

---

## 13. The ask

**Stage:** pre-seed / grant-only.

**Raising:** ₹2.5–3.5 cr non-dilutive (grants + CSR), 12–18 months runway. *No equity before the first state welfare-board contract converts — grants are cheaper capital and preserve the freedom to choose a partner rather than take one.*

**Use of funds:**

| Bucket | Share | What it buys |
|---|---|---|
| Team | ~55% | Policy/GR lead, second engineer, part-time content editors (Hindi/Bengali/Tamil), founder salary |
| Legal & compliance | ~15% | Labour-lawyer retainer for fact-card review, DPDP compliance, professional indemnity insurance, terms drafting |
| Field validation & partnerships | ~15% | NGO-partnered moderated sessions, welfare-board and union relationship-building, travel |
| Infrastructure & compute | ~10% | Cloud Run, Postgres, Gemini + Sarvam usage, on-prem OCR hosting |
| Buffer | ~5% | — |

**Milestones this funds:**
- All five modules live, lawyer-reviewed, deployed (6 weeks).
- Moderated validation with 15–20 workers across 3 languages (90 days).
- Karnataka welfare-board MoU (9 months).
- 1,000 first-time workers, 15% complaint-response rate measured (6 months).
- A published contract-clause evidence brief (12 months).

**What a funder gets:** the first worker-facing product in a market that regulation is actively creating, with the anchor already built, a mission-aligned model that does not depend on the platforms it holds accountable, and a measurement framework that reports initiated-vs-completed honestly.

---

## 14. Non-goals

v1 or ever:

- **Legal advice or representation.** We inform and prepare self-help documents; we do not advise on the merits of a dispute or appear for anyone.
- **Filing complaints on the worker's behalf.** We draft; the worker submits.
- **Guaranteeing benefit disbursement or complaint outcomes.** We surface eligibility and route correctly; the state and the authority act.
- **Mediating between worker and platform.** We route to the right authority; we are not an arbitrator.
- **Case law.** Statutes and schemes only.
- **Selling worker data.** Never, even anonymised.
- **Open ad networks.** Curated sponsor allowlist only ([MONETIZATION.md](MONETIZATION.md) §6.3).
- **Union organising tooling, payment/earnings tracking, job discovery, contract drafting.** Not our niche.

---

## 15. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Solo-founder capacity | High | High | Funding's first use is a policy hire + second engineer; anchor already shipped; advisory board on funding |
| Welfare-board sales cycle (9–18 months) outlasts grant runway | Medium | High | Start Karnataka on day one; grant stack sized for 18 months; insurance channel is independent of any single board |
| Translation quality worse than expected in Bengali/Tamil | Medium | High | Lawyer + back-translation review of all cards; idiom library; audio + English fallback per card; comprehension testing before launch |
| An inaccurate Contract Reader output misleads a worker | Medium | High | Operational labels not legal verdicts; deterministic sanitiser; primary-statute link on every clause; incident/re-review process; E&O insurance |
| Aggregator lobbies against Sreshtha | Medium | Medium | Union + welfare-board endorsements; worker access never gated by a platform; independent complaint routing is non-negotiable |
| Government builds an in-house equivalent | Low–Medium | Medium | Faster iteration, better UX, the idiom corpus moat; position as the software layer that makes the board's mandate usable, not a competitor |
| Chatbot compute cost outruns revenue | Medium | High | Retrieval-first + soft LLM cap + sponsored placements; modelled to stay under ₹15/user/month at 5M users ([MONETIZATION.md](MONETIZATION.md) §6) |
| OTP-only identity loses migrant workers' data on SIM change | Was high in v0.1 | High | Recovery PIN + optional email + one-tap vault export (§7.5) |
| Voice unusable on noisy streets / in dialect | Medium | Medium (not launch-blocking) | Voice deferred past launch; when shipped, transcript shown for confirmation before the pipeline runs; text always works |

---

## Appendix A — Research sources

NITI Aayog, *India's Booming Gig and Platform Economy* (2022). Fairwork India Annual Report 2024. IFAT surveys 2023–24. Ola Mobility Institute, *Working Conditions of Delivery Workers* (2023). Ministry of Labour and Employment, Code on Social Security 2020, Rules 2024. Government of Karnataka, Platform-Based Gig Workers (Social Security and Welfare) Ordinance 2025. Government of Rajasthan, Platform-Based Gig Workers (Registration and Welfare) Act 2023. e-Shram portal data (Q2 2024). India Labourline (1800-419-1550).

## Appendix B — Prior art in this codebase

- **QuickBites Support Bot** — the substrate: Cardinal pipeline, deterministic Stage-2 validator, response library, multi-provider LLM abstraction, admin panel, tenant config. Retargeted for the gig-worker domain.
- **thought-translate** — three-stage translation reasoning (Understand → Research → Synthesise), ported into Contract Reader.

## Appendix C — Companion documents

- [MONETIZATION.md](MONETIZATION.md) — six-channel revenue model, chatbot cost-trap analysis, free-tier limits, unit economics, capital-raise shape.
- [STATUS_2026-08-23.md](STATUS_2026-08-23.md) — build snapshot against the original 20-day plan.
- [DESIGN.md](DESIGN.md) — Cardinal pipeline internals.
- [RIGHTS_GUIDE_CONTENT_GUIDELINES.md](RIGHTS_GUIDE_CONTENT_GUIDELINES.md) — fact-card authoring + review standard.

## Appendix D — Open questions

1. Domain — `sreshtha.app` / `sreshtha.in`.
2. OTP provider — MSG91 or Twilio (affects auth build).
3. Labour-lawyer partner — retainer vs. pro-bono via a legal-aid clinic.
4. First welfare-board contact — direct or via Fairwork India / IIIT-B.
5. Grant sequencing — which funder to approach first given 3–6 month cycles.

## Appendix E — Architectural decision log

A running log of the architectural pivots taken during build. Each row states what changed, the immediate reason, and what would reverse it. Chronological.

| Date | Decision | Reason | Reversal condition |
|---|---|---|---|
| 2026-08-15 | On-prem OCR (EasyOCR + PyMuPDF) replaces Gemini Vision | Zero per-scan cost + worker documents never leave our infrastructure + a path to India-specific fine-tuning | Rare-script quality falls below acceptable and the funded plan can't cover the OCR-tuning line item |
| 2026-08-15 | Gemini owns reasoning, Sarvam Mayura owns translation | Simpler tone control from one reasoning provider; Sarvam Mayura best-in-class for Indic register control | Superseded 2026-09-04 by the per-stage hybrid |
| 2026-08-19 | Idiom substitute/restore sandwich (`app/translate/idioms.py`) wraps every Mayura call | Legal idioms literalise catastrophically ("at the end of the day" → 11:59 pm); a curated library preserves fidelity through a general-purpose translator | Never — this is a compounding moat |
| 2026-08-22 | Chunked Mayura translation with boundary tokens (`[[ROW_n]]`, `[[FLD]]`) | 94-clause contract went from ~11 min sequential to ~30 s batched | Never — this is a hard rate-limit constraint |
| 2026-08-23 | Multi-tenant `tenant_id` on every content row, migration 012 for `tenants` + `tenant_memberships` + bootstrap script | White-labeling welfare boards and unions requires this before any partnership can be piloted | Never — the schema is nullable-tenant-friendly, single-tenant deployments still work |
| 2026-08-24 | License changed from MIT to proprietary "all rights reserved" | The advocacy features require compliance controls and a supervised distribution path; permissive licensing is inconsistent with §6.2 posture | If Sreshtha ever hands the core to a public-interest foundation, this reverses to a copyleft license |
| 2026-09-04 | AI Studio bare-key access (`GEMINI_API_KEY`) removed | Google blocked the key path (`API_KEY_SERVICE_BLOCKED`) despite billing being current | Never — Vertex is the only reliable Google path |
| 2026-09-04 | `LLM_PROVIDER` default switched from Gemini to OpenAI; Vertex kept as an explicit swap | AI Studio path blocked; ADC-through-Vertex works but has more setup friction for local dev; OpenAI is available and reliable | Vertex quota + billing setup completes across all deployment machines |
| 2026-09-04 | **Per-stage hybrid reasoning**: Stage 1 gpt-4o-mini with Structured Outputs (+ 4o fallback), Stage 2 gpt-4o + RAG, Stage 3 Vertex Gemini + chunked parallel | ML research: mini at effective parity with 4o on structured extraction at ~15× lower cost; 4o superior for reasoning-heavy annotation with RAG-grounded citations; Gemini's warmer register better upstream for Mayura translation | If A/B measurement shows quality drop on Stage 1 (fallback rate > 15%) OR RAG grounding on Stage 2 does not materially improve citation accuracy vs pure gpt-4o baseline |
| 2026-09-04 | Contract Reader language scope for v1 tightened to Hindi + Bengali + English | Quality-preserving scope: idiom library coverage and native-speaker review are the gates on adding a language; both are still building for TA/TE/KN/MR | Idiom coverage reaches ≥100 entries per language AND Rights Guide native review completes for that language |
| 2026-09-04 | **No-shot rule library** (`clause_rules`) chosen over few-shot exemplar library for Stage 3 response generation | Legal reasoning is rule-shaped; authoring one rule spec is ~5× the throughput of curating exemplars; a lawyer can review 20 rule specs where they cannot review 100+ exemplar outputs; rule rows carry versioning and reviewer provenance | A/B measurement finds the library hit rate below 50% AND novel-clause quality lags a pure-LLM baseline |
| 2026-09-04 | Embedding model for the statute corpus: `text-embedding-3-large` at 1024 dimensions via Matryoshka Representation Learning | Highest-quality legal-domain OpenAI embedding, MRL-reduced to a footprint lower than `text-embedding-3-small` at 1536 dims, at one-time embedding cost < $0.10 | A specialist legal embedding (voyage-law-2 or similar) with a compliant privacy posture becomes available |
| 2026-09-04 | pgvector index: HNSW | Consensus across four benchmark sources: HNSW dominates on recall / p99 latency for corpora under 1M rows at negligible memory penalty (~40 MB total for the seed corpus) | Corpus grows beyond ~5M vectors, at which point IVFFlat's memory profile becomes attractive again |
| 2026-09-04 | `GEMINI_FAST_MODEL` changed from `gemini-2.5-flash-lite` to `gemini-2.5-flash` | Google announced Flash-Lite retirement 2026-10-16; Flash is already cheap enough that the role collapse costs nothing meaningful | Google publishes a successor Flash-Lite variant with better pricing |

---

*End of PRD v0.2.*
