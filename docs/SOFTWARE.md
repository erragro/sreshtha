# Sreshtha — Software Documentation

**A web app for India's gig workers: contract explanations, rights guidance,
and welfare-scheme discovery, in the languages workers actually read.**

This document describes what is built and how it works (September 2026). It is
the technical companion to [`PRD.md`](PRD.md) (product requirements),
[`DESIGN.md`](DESIGN.md) (design notes), and
[`CLOUD_RUN_DEPLOYMENT.md`](CLOUD_RUN_DEPLOYMENT.md) (the authoritative
production deployment + troubleshooting guide).

---

## Table of contents

1. [System overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Repository layout](#3-repository-layout)
4. [Runtime & configuration](#4-runtime--configuration)
5. [Data model](#5-data-model)
6. [Authentication & authorization](#6-authentication--authorization)
7. [Module: Contract Reader](#7-module-contract-reader)
8. [Module: Rights Guide](#8-module-rights-guide)
9. [Module: Schemes Finder](#9-module-schemes-finder)
10. [Module: Chatbot Sahaayak (disabled)](#10-module-chatbot-sahaayak-disabled)
11. [Module: Complaint Helper (planned)](#11-module-complaint-helper-planned)
12. [Translation subsystem](#12-translation-subsystem)
13. [Retrieval / RAG](#13-retrieval--rag)
14. [Admin surfaces](#14-admin-surfaces)
15. [Frontend](#15-frontend)
16. [Observability & logging](#16-observability--logging)
17. [Testing](#17-testing)
18. [Deployment](#18-deployment)
19. [Known limitations & roadmap](#19-known-limitations--roadmap)
20. [Recent changes](#20-recent-changes)

---

## 1. System overview

Sreshtha is a mobile-responsive single-page web app backed by a FastAPI
service and a PostgreSQL database. A gig worker signs up with an email and
password and gets access to three live modules:

| Module | What it does | Status |
|---|---|---|
| **Contract Reader** | Upload the contract you signed with an aggregator; get it broken down clause by clause, risk-tiered, and rewritten in plain language in your own language. | Live |
| **Rights Guide** | Curated, statute-cited fact cards on wages, injury, grievance escalation, e-Shram, and reading a contract. | Live (English content; other languages fall back to English) |
| **Schemes Finder** | Answer a short profile wizard, see which central/state welfare schemes are worth checking, with the documents and portal link for each. | Live (English content) |
| **Chatbot Sahaayak** | A conversational helper. | **Disabled** — see §10 |
| **Complaint Helper** | Draft a complaint routed to the right authority. | **Planned** — content only, no worker route (§11) |

The reasoning stack (contract analysis) runs on OpenAI by default, with an
optional Google Vertex AI (Gemini) path. Indic translation runs on Sarvam
Mayura. OCR for photos/scans runs locally on Tesseract. All worker-facing
surfaces speak seven languages in principle (English, Hindi, Bengali, Tamil,
Telugu, Kannada, Marathi); the amount of translated *content* currently
shipped varies by module (§12).

### Origin

The codebase began as a customer-support chatbot ("QuickBites / Cardinal", a
5-phase + 4-stage synchronous LLM pipeline). Sreshtha was built on top of that
foundation, reusing the auth, session, module-registry, and LLM-provider
infrastructure. The legacy chat pipeline (`app/l1_cardinal/`, `app/l2_agents/`)
and its database tables (`customers`, `orders`, `riders`, `restaurants`, …)
are still present but the chat module is disabled and not exposed to workers.

---

## 2. Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  Browser (React 19 SPA)                                             │
│  React Router · TanStack Query · Zustand (auth) · Tailwind v4       │
└───────────────┬────────────────────────────────────────────────────┘
                │  same-origin  /api  /auth  /run  /ping
┌───────────────▼────────────────────────────────────────────────────┐
│  nginx (frontend container)                                         │
│  · serves the built SPA, SPA-fallback routing                       │
│  · reverse-proxies /api, /auth, /run, /ping → ${API_UPSTREAM}       │
│    (app:8000 under compose; the sreshtha-api URL in production)     │
└───────────────┬────────────────────────────────────────────────────┘
┌───────────────▼────────────────────────────────────────────────────┐
│  FastAPI (app container, uvicorn)                                   │
│                                                                    │
│  auth/        JWT signup/login/me, bcrypt, slowapi rate limits     │
│  modules/     module registry + per-user ACL + super-admin         │
│  contracts/   Contract Reader — upload → extract → 3 stages → i18n  │
│  rights/      Rights Guide fact-card API                           │
│  schemes/     Schemes Finder wizard + eligibility matcher          │
│  translate/   Sarvam Mayura wrapper + idiom sandwich               │
│  retrieval/   pgvector similarity search over the statute corpus   │
│  l1_cardinal/ } legacy chat pipeline (disabled)                    │
│  l2_agents/   } LLM agents + provider abstraction                  │
│  conversation_studio/  admin CRUD for chat taxonomy               │
│  idioms/      idiom-library admin                                  │
└───────────────┬────────────────────────────────────────────────────┘
      ┌─────────┼─────────────────────┬───────────────────┐
┌─────▼─────┐ ┌─▼──────────┐  ┌───────▼────────┐  ┌───────▼────────┐
│ Postgres  │ │  OpenAI    │  │ Sarvam Mayura  │  │  Tesseract     │
│ 16 +      │ │  (or       │  │ (Indic trans-  │  │  (local OCR,   │
│ pgvector  │ │  Vertex AI)│  │  lation)       │  │  in-process)   │
└───────────┘ └────────────┘  └────────────────┘  └────────────────┘
```

### Tech stack

**Backend** — Python 3.11 (3.13 in local dev), FastAPI, SQLAlchemy 2 (sync
sessions), Alembic, Pydantic v2 / pydantic-settings, `psycopg` v3, `slowapi`
(rate limiting), `python-jose` (JWT), `bcrypt`. LLM clients: `openai`,
`google-genai` (Vertex). Text extraction: `pytesseract` (+ system `tesseract`),
`PyMuPDF` (PDF), `Pillow` (images), stdlib `zipfile` (`.docx`). Idiom matching:
`pyahocorasick`.

**Frontend** — React 19, Vite 8, TypeScript, Tailwind CSS v4, shadcn/ui
(Radix primitives), `@tanstack/react-query`, `react-router-dom`, `zustand`,
`axios`, `motion` (animation), `sonner` (toasts), `lucide-react` (icons).

**Database** — PostgreSQL 16 with the `pgvector` extension (image
`pgvector/pgvector:pg16`).

**Infra** — Docker Compose for local/self-host. Production is two Cloud Run
services (`sreshtha-api`, `sreshtha-web`) fed by **manual** local Docker
builds pushed to Artifact Registry, backed by Cloud SQL + Secret Manager +
Cloud Storage. See [`CLOUD_RUN_DEPLOYMENT.md`](CLOUD_RUN_DEPLOYMENT.md) — that
document is the source of truth for the deploy process; keep it updated when
the production architecture deliberately changes.

### Request flow

The SPA calls same-origin paths (`/api/...`, `/auth/...`). In dev, Vite
proxies them to `localhost:8000`; in the container, nginx reverse-proxies
them to the `app` service. Every authenticated request carries
`Authorization: Bearer <jwt>`; a `401` clears the client session and the
router redirects to `/login`.

Contract processing is **asynchronous**: `POST /api/contracts/{id}/process`
returns `202` immediately and a FastAPI `BackgroundTask` advances the
contract through its status machine, committing after each stage. The client
polls `GET /api/contracts/{id}` every 2 s until `ready` or `failed`, rendering
each stage's output as it lands.

---

## 3. Repository layout

```
sreshtha/
├── app/                          FastAPI backend
│   ├── main.py                   app entrypoint, router wiring, logging, startup
│   ├── config.py                 pydantic-settings (reads .env)
│   ├── db.py                     SQLAlchemy engine + session helpers
│   ├── models.py                 all ORM models
│   ├── schemas.py                shared pydantic schemas
│   ├── migrations/bootstrap.py   startup: create legacy schema, seed, alembic upgrade
│   ├── auth/                     JWT, password hashing, dependencies, routes
│   ├── modules/                  module registry + per-user access control + admin
│   ├── contracts/                Contract Reader (see §7)
│   ├── rights/                   Rights Guide fact-card API
│   ├── schemes/                  Schemes Finder wizard + matcher
│   ├── translate/idioms.py       idiom substitute/restore around Mayura
│   ├── retrieval/                embeddings + pgvector retrieval for Stage 2 RAG
│   ├── l1_cardinal/              legacy chat pipeline (5 phases) — disabled
│   ├── l2_agents/                legacy chat agents + llm_provider abstraction
│   ├── conversation_studio/      admin CRUD for chat taxonomy + chat-starter API
│   ├── idioms/                   idiom-library admin API
│   ├── sessions/                 chat session CRUD (gated by chatbot_enabled)
│   ├── runners/, simulator_client.py   legacy eval/simulator harness
│   └── policies/                 legacy policy-file loader (chat only)
├── alembic/versions/             001–016 migrations
├── data/app.db                   SQLite seed for legacy starter tables
├── frontend/                     React SPA (Vite), nginx.conf, Dockerfile
├── scripts/                      bootstrap_tenant, translate_rights_guide, translate_schemes, …
├── tests/                        pytest suite
├── docs/                         PRD, DESIGN, content guidelines, this file
├── Dockerfile                    production API image (root) — used for sreshtha-api
├── Dockerfile.cloudrun           bundled-Postgres variant — NOT used by the current prod deploy
├── docker-compose.yml            local/self-host stack
├── frontend/Dockerfile           production web image — used for sreshtha-web
└── cloudbuild.yaml               legacy Cloud Build config — NOT part of the current manual deploy
```

---

## 4. Runtime & configuration

### Local (Docker Compose)

```bash
cp .env.example .env          # fill OPENAI_API_KEY + SARVAM_API_KEY
docker compose up --build
```

Three containers come up:

| Service | Port | Notes |
|---|---|---|
| `frontend` (nginx) | `${FRONTEND_PORT:-5173}` → 80 | built SPA + reverse proxy |
| `app` (uvicorn) | 8000 | FastAPI; runs Alembic on startup |
| `postgres` (pgvector/pg16) | 5435 → 5432 | volume `pgdata` |

On first boot the `app` container runs `app/migrations/bootstrap.run()`:

1. **Create the legacy starter schema** — `customers`, `restaurants`, `riders`,
   `orders`, `order_items`, `refunds`, `reviews`, `rider_incidents`, … (raw
   DDL; these back the disabled chat pipeline).
2. **Seed** those tables from `data/app.db` (SQLite) if empty.
3. **`alembic upgrade head`** — migrations 001–016 create every runtime table
   (auth, modules, contracts, fact cards, schemes, idioms, tenants, embeddings,
   clause rules) and seed shared content (clause rules, statute corpus, the
   five fact cards, the ten schemes).

`docker compose down -v` drops the database volume and everything reseeds on
the next boot.

### Backend without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d postgres
alembic upgrade head
uvicorn app.main:app --port 8000 --reload
```

`tesseract` must be on `PATH` for photo/scan OCR (`brew install tesseract
tesseract-lang` on macOS). Text, `.docx`, and born-digital PDFs work without it.

### Frontend without Docker

```bash
cd frontend && npm install && npm run dev     # http://localhost:5173
```

### Configuration (`app/config.py`, read from `.env`)

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | local Postgres | SQLAlchemy connection string (`postgresql+psycopg://…`) |
| `LLM_PROVIDER` | `""` (= OpenAI) | reasoning provider: `""` / `openai` / `vertex` |
| `OPENAI_API_KEY` | — | required for the default reasoning path |
| `OPENAI_FAST_MODEL` / `OPENAI_SMART_MODEL` | `gpt-4o-mini` / `gpt-4o` | logical `fast`/`smart` roles |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | override for a proxy/gateway |
| `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION` | — / `asia-south1` | Vertex AI; auth via ADC (`GOOGLE_APPLICATION_CREDENTIALS`) |
| `GEMINI_FAST_MODEL` / `GEMINI_SMART_MODEL` | `gemini-2.5-flash-lite` / `gemini-2.5-flash` | Vertex model ids |
| `SARVAM_API_KEY` | — | Sarvam Mayura translation |
| `SARVAM_*_MODEL`, `SARVAM_MAX_TOKENS_CAP` | `sarvam-105b-conversations`, `4096` | translation model + token ceiling |
| `GOOGLE_TRANSLATE_API_KEY` | `""` | language detection (chat pipeline only; falls back to `en`) |
| `JWT_SECRET` | unsafe marker | **must** be overridden outside local; boot refuses in non-`local` `APP_ENV` |
| `JWT_ACCESS_TTL_MINUTES` | `1440` (24 h) | access-token lifetime |
| `AUTH_SIGNUP_RATE` / `AUTH_LOGIN_RATE` | `10/hour` / `30/hour` | per-IP slowapi limits |
| `SUPER_ADMIN_EMAIL` | `""` | first signup matching this email becomes super-admin; if unset, the first user to sign up is super-admin |
| `DEFAULT_MODULE_KEYS` | `contract_reader,rights_guide,schemes_finder` | modules a new user gets `view` on |
| `CHATBOT_ENABLED` | `false` | gates the legacy chat endpoints (§10) |
| `CONTRACT_STORAGE_ROOT` | `./data/contracts` | local dir, or `gs://bucket/prefix` for GCS |
| `CONTRACT_MAX_BYTES` | `10 MB` | upload ceiling (nginx allows 20 MB at the edge) |
| `APP_ENV` | `local` | set by the container manifest; non-`local` enforces JWT-secret + prod behaviour |

---

## 5. Data model

All tables live in one Postgres database. UUID primary keys throughout;
`created_at`/`updated_at` timestamps on most rows. Grouped by concern:

### Auth & access control

| Table | Key columns | Notes |
|---|---|---|
| `users` | `email` (unique), `hashed_password`, `is_active`, `is_super_admin`, `created_at` | bcrypt hash; super-admin is orthogonal to module access |
| `modules` | `key` (unique), `name`, `description`, `icon`, `path`, `is_system`, `sort_order` | the registry of module definitions; seeded by migration 003/011 |
| `user_module_access` | `(user_id, module_id)` unique, `access_level` ∈ `view\|edit\|admin`, `granted_by` | per-user grant; ranked, idempotent upgrades |

### Rights Guide / Schemes / Complaint content

| Table | Key columns | Notes |
|---|---|---|
| `fact_cards` | `(topic_key, language, tenant_id)` unique, `title`, `summary`, `citation`, `action_steps` (JSONB), `icon`, `audio_url`, `is_active`, `sort_order` | one row per (topic, language); `language ∈ en/hi/bn/ta/te/kn/mr` |
| `schemes` | `key` unique per tenant, `state_scope` (`central\|all\|<state>`), `eligibility_rules` (JSONB), `docs_needed` (JSONB), `apply_url`, `estimated_time`, `icon` | language-agnostic metadata |
| `scheme_translations` | `(scheme_id, language)` unique, `name`, `description`, `apply_note` | per-language scheme copy |
| `complaint_templates` | template body + placeholders | seeded (migration 011); **not read by any live route** |

### Contract Reader

| Table | Key columns | Notes |
|---|---|---|
| `uploaded_contracts` | `user_id`, `filename`, `mime_type`, `size_bytes`, `storage_key`, `status`, `ocr_text`, `stages` (JSONB), `language` (source), `target_language`, `target_script`, `translation_mode`, `processing_consent`, `contract_type`, `error_message`, `tenant_id` | see §7; `status` CHECK-constrained to the state machine; `target_language`/`translation_mode` CHECK-constrained to the supported sets |
| `clause_rules` | `slug`, `name`, `description`, `contract_types`, `default_risk_tier`, `citation`, `topic_hint`, `generation_rules`, `forbidden_content`, `required_content`, `safe_fallback`, `is_active`, `tenant_id` | deterministic rewrite rules for common clause patterns (Stage 3); seeded by migrations 014/015 |
| `embeddings` | `content`, `embedding` (`vector(1024)`), `source_type`, `source_ref`, `metadata` (JSONB), `tenant_id` | statute corpus for Stage 2 RAG; seeded by migration 013 |

### Idiom library

| Table | Key columns | Notes |
|---|---|---|
| `idiom_library` | `phrase` (English), `meaning`, `category`, `is_active` | ~75 seeded entries |
| `idiom_translations` | `(idiom_id, language)`, `equivalent` | pre-verified target-language equivalent used in the translation sandwich |

### Multi-tenancy

| Table | Key columns | Notes |
|---|---|---|
| `tenants` | `slug`, `name`, `kind` (`welfare_board\|union\|sponsor\|ngo`), `tagline`, `primary_color` | a partner deployment |
| `tenant_memberships` | `(user_id, tenant_id)`, `role` | a user can belong to several tenants |

Every content row (`fact_cards`, `schemes`, `clause_rules`, `embeddings`,
`idiom_*`, `uploaded_contracts`) carries a nullable `tenant_id`:
`NULL` = shared library visible to everyone (the default seed);
`<uuid>` = a tenant-specific override or addition.

### Legacy chat (present, mostly unused)

`chat_sessions`, `turns`, `bot_executions`, `business_units`, `issue_types`,
`data_point_registry`, `issue_type_data_points`, `acknowledgment_templates`,
`intent_detection_cases`, plus the SQLite-seeded `customers` / `orders` /
`order_items` / `restaurants` / `riders` / `rider_incidents` / `refunds` /
`reviews`. `chat_sessions`/`turns` are still written by the (gated) session
CRUD; the rest are only touched by the disabled chat pipeline and the
Conversation Studio admin.

---

## 6. Authentication & authorization

### JWT auth

- **`POST /auth/signup`** `{email, password}` → creates the user (bcrypt
  hash), applies default module access, maybe promotes to super-admin, returns
  `{access_token, token_type, user}`. Rate-limited (`10/hour`/IP).
- **`POST /auth/login`** `{email, password}` → constant-time password check;
  identical error whether the email exists or not (blocks enumeration);
  returns a fresh token. Rate-limited (`30/hour`/IP).
- **`GET /auth/me`** → the current user (used by the SPA after a page reload).

Tokens are HS256, `iss=sreshtha`, 24 h TTL. The client stores the token in
`localStorage` (zustand `persist`) and attaches it to every request via an
axios interceptor. A `401` response clears the session.

### Module access control

Access is a `(user, module, level)` grant with `level ∈ view < edit < admin`,
stored in `user_module_access`. A new user is granted `view` on the keys in
`DEFAULT_MODULE_KEYS` (`contract_reader`, `rights_guide`, `schemes_finder`).

`GET /api/modules` returns every module with the caller's `access_level`
(or `null`). Enforcement is:

- **Frontend** — `ModuleGuard` redirects to `/` when the module isn't
  granted; `MainSidebar.tsx` / `HomePage.tsx` filter the nav and home cards
  to a hard-coded worker-ready set (`contract_reader`, `rights_guide`,
  `schemes_finder`), so `chatbot` and `complaint_helper` never appear even
  though `/api/modules` still lists them.
- **Backend** — the content routes (`/api/rights/*`, `/api/schemes/*`,
  `/api/contracts/*`) currently require only **authentication**
  (`get_current_active_user`), not a module grant. Contract rows are
  user-scoped (a contract you don't own returns `404`). Module access is a
  navigation/UX gate, not an API authorization boundary today;
  `/api/admin/*` is the one surface with a hard server-side check
  (`is_super_admin`). The chat endpoints add a server-side
  `CHATBOT_ENABLED` gate (§10).

### Super-admin

`is_super_admin` is a separate flag, gating `/api/admin/*` and the admin SPA
routes. The first signup that matches `SUPER_ADMIN_EMAIL` (or simply the first
user, if that env var is unset) is promoted automatically.

### Multi-tenancy

`scripts/bootstrap_tenant` provisions a tenant + owner user:

```bash
python -m scripts.bootstrap_tenant \
    --slug karnataka-welfare \
    --name "Karnataka Platform Gig Workers Welfare Board" \
    --kind welfare_board \
    --admin-email owner@example.gov.in \
    --tagline "Powered by Sreshtha" \
    --primary-color "#5b3fd6"
```

Content queries return `tenant_id IS NULL` rows plus the caller's tenant rows.

---

## 7. Module: Contract Reader

The anchor module. A worker uploads the agreement they signed with an
aggregator and gets, in their language: a clause-by-clause breakdown, a
red/amber/green risk tier per clause with a statute citation, a plain-language
rewrite of each clause, "what this means for you", and a concrete action —
plus a top-of-page summary and the three highest-priority actions.

### 7.1 Upload & validation — `app/contracts/service.py`

`POST /api/contracts` (multipart):

| Field | Required | Values |
|---|---|---|
| `file` | yes | PDF, JPG/JPEG, PNG, **`.txt`**, **`.docx`** — max 10 MB |
| `target_language` | yes | `en\|hi\|bn\|ta\|te\|kn\|mr` (worker-facing UI currently offers `hi\|bn\|en`) |
| `target_script` | no | `native` (default) or `roman` (roman not yet implemented → 400) |
| `source_language` | no | OCR hint for photos/scans |
| `translation_mode` | no | `formal` (default) / `modern-colloquial` / `classic-colloquial` / `code-mixed` |
| `processing_consent` | no (default `false`) | must be `true` before processing can start |

Validation order: language/script/mode checks → MIME check → read bytes →
empty check → size ceiling → **content signature check**.

- **MIME resolution.** The declared `Content-Type` is used directly if it is
  in the whitelist. If it is generic/empty (`""`,
  `application/octet-stream`, `application/zip`, `binary/octet-stream`) the
  real type is recovered from the **filename extension** — some browsers and
  mobile OSes send a generic type for `.txt`/`.docx`. An explicitly wrong
  type (e.g. `application/msword` for a `.doc`) is rejected as unsupported.
- **Signature check** (`_matches_declared_mime`): PDF `%PDF-`, JPEG
  `FF D8 FF`, PNG `89 PNG …`, `.docx` `PK\x03\x04` (zip), `.txt` decodes as
  text with no NUL bytes in the first 8 KB.

On success a row is inserted in `status = "uploaded"` with the raw file
written to storage (`LocalStorage` under `contract_storage_root`, or GCS when
the root is a `gs://` URL). Upload does **not** auto-start processing.

### 7.2 Text extraction — `app/contracts/ocr.py`

`extract_text(file_bytes, mime_type, *, source_language)` → `OCRResult(text,
language, is_low_quality)`. Branches by type:

| Type | Path |
|---|---|
| `text/plain` | decode (`utf-8-sig` → `utf-16` → `utf-8` → `cp1252` → `latin-1`). No OCR. |
| `.docx` | `zipfile` → read `word/document.xml` (bounded to 40 MB decompressed) → regex: `<w:br/>`/`<w:tab/>` become whitespace runs, split on `</w:p>`, lift `<w:t>` text, unescape the 5 XML entities. No XML parser → no entity-expansion attack surface. No OCR. |
| `application/pdf` | **text layer first** (`PyMuPDF` `page.get_text`). If the layer yields ≥ 80 chars, done — no OCR. Otherwise rasterise every page at 300 dpi and OCR. |
| `image/png`, `image/jpeg` | decode with Pillow → OCR. |

**OCR engine: Tesseract** via `pytesseract`. The `tesseract` binary and the
`eng hin ben tam tel kan mar` traineddata ship in the Docker image, so there
is no model download on first use and behaviour is identical on x86 and ARM.
Language routing (`_tesseract_lang_for`): `en` (or no usable hint) → `eng`;
a named Indic language → `eng+<lang>` (e.g. `eng+hin`) so bilingual contracts
read on both scripts.

> **History:** OCR was previously EasyOCR (PyTorch). That stack produced
> garbled output on the ARM64 build and pulled ~1 GB of wheels plus a runtime
> model download. Tesseract replaced it in the September 2026 release.

### 7.3 Processing state machine — `app/contracts/processor.py`

`POST /api/contracts/{id}/process` → `409` unless `processing_consent` is
recorded and `status ∈ {uploaded, failed}`; otherwise sets `status =
ocr_pending`, schedules `process_contract_bg` as a `BackgroundTask`, returns
`202`.

```
uploaded ──► ocr_pending ──► ocr_done ──► processing ──► ready
                  │              │            │             ▲
                  └──────────────┴────────────┴──► failed ───┘  (retry)
```

Each transition **commits** before the next stage runs, so a crashed worker
leaves the row at a resumable state. Failures set `status = failed` and a
plain-language `error_message` (never a stack trace). Re-running `/process`
on a `failed` row clears the error and retries from scratch.

Stage failure policy:

| Stage | On error |
|---|---|
| OCR / storage read | `failed` |
| Stage 1 (no clauses identified) | `failed` — "We could not identify contract clauses…" |
| Stage 2 | **soft** — persist the error, continue to Stage 3 with empty annotations |
| Stage 3 (a whole render batch fails) | `failed` — "We could not prepare a plain-language explanation…" |
| Translation | **soft** — row still becomes `ready`; the viewer falls back to the English Stage 3 output, and the response carries a "shown in English" note |

### 7.4 Stage 1 — extract — `app/contracts/stage1.py`

One structured-output call (OpenAI `gpt-4o-mini`, retry on `gpt-4o`). Input:
the OCR text. Output JSON:

- `clauses[]` — `{id, text, heading, section_number}`
- `metadata` — `{parties[], jurisdiction, effective_date, signature_date, governing_language, term}`
- `contract_type` — `aggregator` / `platform` / `staffing` / … / `unknown`
- `confidence` — 0–1

Reasoning is always in English regardless of the contract's language.

### 7.5 Stage 2 — annotate + risk — `app/contracts/stage2.py`

Clauses are batched 5 per call across a 6-worker thread pool (OpenAI
`gpt-4o`, `role="smart"`). **RAG-grounded:** for each batch, the statute
corpus (`embeddings` table) is queried by cosine similarity
(`k = 3` per clause, similarity floor `0.30`) and the retrieved chunks are
spliced into the annotator prompt so it cites *what it saw*, not statute
numbers from parametric memory.

Output per clause: `{clause_id, risk: red|amber|green, note, citation:
{name, section, url}, topic_hint}`. Rules the prompt enforces: every input
clause gets an annotation; boilerplate is `green` with null citation; if no
statute applies, all citation fields are null (no invented citations);
`topic_hint` links a clause to a Rights Guide topic when relevant.

**Jurisdiction guard:** a small explicit map of state-specific instruments
(Karnataka / Rajasthan platform-gig-worker laws). A state statute is only
allowed through if the contract's `metadata.jurisdiction` matches, so a
familiar state law can't be presented as nationwide.

### 7.6 Stage 3 — synthesise (worker-facing rewrite) — `app/contracts/stage3.py`

Produces, for each clause, three short English strings — `explanation`
(plain-language rewrite), `implication` (what it means for the worker),
`action` (a concrete step, or `null`) — plus a document `overview`
(`top_summary` + up to 3 `top_actions`).

1. **Classify** — one `gpt-4o-mini` call maps every clause to a `clause_rules`
   slug or `novel`.
2. **Render** — clauses are chunked and rendered in parallel:
   - **`library-rule`** — a matched `clause_rules` row supplies deterministic
     `generation_rules` / `required_content` / `forbidden_content` / a
     citation and a `safe_fallback`. The rule's jurisdiction is checked
     (`_rule_applies_in_jurisdiction`) before its state-specific citation is
     used.
   - **`novel-llm`** — the configured reasoning provider renders the clause
     under the same constraints, validated against a per-clause validator
     (`stage3_validator`).
   - A clause that fails both falls back to `safe_fallback` text.
3. **Overview** — the reasoning provider summarises the whole rendered set.

The generator uses `get_provider("en")` — it **follows `LLM_PROVIDER`** like
Stages 1 and 2. (It was previously pinned to Vertex, which made every rewrite
fail on the default OpenAI path; fixed September 2026.)

If any render batch throws, `_chunk_failure_error` sets a non-null `error`
on the stage output and the processor marks the contract `failed` with a
retryable message, rather than serving a "completed" read full of fallback
placeholders.

### 7.7 Translation — `app/contracts/translate.py`

When `target_language != "en"`, the processor calls:

- `translate_stage_3(rendered, target_language, mode)` — batches clause rows
  into Sarvam-cap-friendly chunks (`≤ 800` input chars) with opaque row/field
  markers (`[[ROW_n]]` / `[[FLD]]`), wraps each chunk in the idiom
  substitute/restore sandwich (§12), and translates via Mayura. A failed
  chunk degrades **per row** to the English source (marked
  `translation_fallback`), never aborting the whole batch.
- `translate_overview(overview, target_language, mode)` — translates
  `top_summary` and each `top_action` individually (best-effort; any field
  that fails stays English). *(Added September 2026 — previously the overview
  was shown in English even to non-English readers.)*

The result is stored at `stages.stage_3.translation = {language, mode,
rendered, overview, translator, fallback_clause_ids, error}`. The viewer
prefers `translation.rendered` / `translation.overview` and falls back to the
English `stage_3.rendered` / `stage_3.overview` when the translation is
missing or fully fell back.

Original clause text (Stage 1) is always kept verbatim in whatever language
the contract was written in; only the analysis is translated.

### 7.8 API surface

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/contracts` | upload (multipart) → `201` row in `uploaded` |
| `POST` | `/api/contracts/{id}/process` | start/retry processing → `202` |
| `GET` | `/api/contracts` | list the caller's contracts (newest first) |
| `GET` | `/api/contracts/{id}` | full detail incl. `ocr_text` + `stages` (poll target) |
| `GET` | `/api/contracts/{id}/download` | stream the original file back |
| `DELETE` | `/api/contracts/{id}` | delete file + row |

Ownership: another user's contract returns `404` (never `403`) so the API
isn't a probe for contract-id existence.

### 7.9 Frontend

`ContractReaderPage.tsx` — language + tone + source-language selectors, a
consent checkbox, a drag-drop upload zone (`accept=".pdf,.jpg,.jpeg,.png,
.txt,.docx"`), and the list of the user's contracts with a status pill and
"Read this contract" / retry / delete actions. `useContracts.ts` polls the
list every 2 s while any row is non-terminal.

`ContractDetailPage.tsx` — the "At a glance" tier counts, the (translated)
overview card, and one card per clause showing the clause heading, the
plain-language explanation, "What this means for you", a suggested action,
the risk badge, the statute citation with a "View source" link, and a
"Show original clause" disclosure.

---

## 8. Module: Rights Guide

Curated fact cards on Indian gig-worker rights. Content-driven, no LLM at
request time.

- **`GET /api/rights/cards?language=<lang>`** → the active cards for that
  language, sorted. If the language has **no** active cards, falls back to
  English and the response flags `language_fallback`.
- **`GET /api/rights/cards/{topic_key}?language=<lang>`** → one card; falls
  back to the English canonical for that topic if the requested language
  isn't active yet.

Seeded topics (migration 009): `minimum_wage`, `injury_on_the_job`,
`grievance_escalation`, `e_shram_registration`, `contract_fairness`. Each card
has a `title`, a prose `summary`, a `citation` string (statute + gazette
link), and structured `action_steps`. Content rules are in
[`RIGHTS_GUIDE_CONTENT_GUIDELINES.md`](RIGHTS_GUIDE_CONTENT_GUIDELINES.md);
the English canonical is in
[`RIGHTS_GUIDE_CONTENT_DRAFT.md`](RIGHTS_GUIDE_CONTENT_DRAFT.md).

**Current content state:** English only. `scripts/translate_rights_guide`
(5 cards × Hindi/Bengali/Tamil via Mayura) exists but has not been run against
the shipped database; non-English languages show "Translation review for this
language is in progress" and the English canonical.

`RightsGuidePage.tsx` — a language selector and the card list.
`RightsGuideDetailPage.tsx` — the full card with citation, action steps, and
the India Labourline helpline (`1800-419-1550`).

---

## 9. Module: Schemes Finder

A short profile wizard that surfaces welfare schemes worth checking. The
matcher is **deterministic** — no LLM.

- **`GET /api/schemes?language=<lang>`** → all active schemes with their
  translation (English fallback if the language isn't populated).
- **`GET /api/schemes/{key}?language=<lang>`** → one scheme with
  `docs_needed`, `estimated_time`, `apply_url`.
- **`POST /api/schemes/match`** `{state, work_type, age, gender,
  has_bank_account, registered_eshram, has_daughter_under_10,
  likely_means_tested_eligible}` → matched schemes, a total count, and a
  short human-readable reason per match ("Available in Karnataka", "Your age
  falls inside the scheme's window") — **informational, never a claim of
  eligibility**.

### Matching logic — `app/schemes/service.py`

For each active scheme:

1. **State-scope prefilter** — drop schemes scoped to a state the worker
   isn't in (`state_scope ∈ {null, all, <the worker's state>}` passes).
2. **Walk `eligibility_rules` (JSONB)** against the profile. Any rule the
   profile doesn't answer is treated as "no filter" (partial profiles still
   get candidates). Recognised rules: `occupations`, `states`,
   `min_age`/`max_age`, `gender`, `requires_bank_account`, `requires_eshram`,
   `requires_daughter`, `means_tested`.

Seeded schemes (migration 010, 10 rows): e-Shram Registration, PM-SYM
(pension), Atal Pension Yojana, PMJJBY, PMSBY, Ayushman Bharat, the Karnataka
Platform Gig Workers Welfare Fund, and others.

**Current content state:** English only (same as Rights Guide;
`scripts/translate_schemes` not yet run against the shipped DB).

`SchemesFinderPage.tsx` — the wizard + inline results.
`SchemeDetailPage.tsx` — documents needed, processing time, and the official
portal link.

---

## 10. Module: Chatbot Sahaayak (disabled)

The chat module is **disabled by default** (`CHATBOT_ENABLED = false`) and is
not exposed to workers:

- `GET /api/chat/starters`, `POST /api/sessions/{id}/select-issue`, and
  `POST /api/sessions/{id}/chat` return **`503`** with a "temporarily
  unavailable" message.
- It is removed from the sidebar, the home page, and the default module
  grants. `/chat/*` in the SPA redirects to `/`.
- Session CRUD (`POST /api/sessions`, list/rename/delete) is **not** gated —
  creating an empty session row is free and costs no model quota.

### Why

The chat pipeline is the inherited "Cardinal" customer-support engine, wired
for a food-delivery company's customers, not gig workers. Its taxonomy
("Missing item", "Food arrived cold", "The rider was rude at the door") is
wrong for the audience, and its Stage 1 evaluator loads a policy file
(`policy_and_faq.md`) that was removed when the repo was retargeted — so
every turn fell through to a "conservative escalation" fallback. It needs its
prompts, taxonomy, and safety rules rewritten for worker rights before it can
be re-enabled.

### The legacy pipeline (`app/l1_cardinal/pipeline.py`)

Retained for the retargeting work. One synchronous call per turn:

```
Phase 1 Validator   → injection / abuse / vagueness gate
Phase 2 Deduplicator→ replay a recent identical turn from cache
Phase 3 Handler     → load/create the session, build history snippet
      (language detect via Google Cloud Translation)
Stage 0 Classifier  → intent + order-id extraction (gpt-4o-mini)
Phase 4 Enricher    → pull order/customer context from the DB
Phase 5 Dispatcher  → escalation group + execution id
Stage 1 Evaluator   → proposed actions + reasoning (gpt-4o)
Stage 2 Validator   → policy hard-rules, override matrix
Stage 3 Responder   → final worker-facing message
```

Any exception in Stage 0–3 is caught and converted to a conservative
`escalate_to_human` response. Conversation Studio (`/api/admin/conversation/*`)
is the admin CRUD for the chip-tap taxonomy (business units → issue types →
data points → templates) that would drive a rebuilt chat UI.

---

## 11. Module: Complaint Helper (planned)

`complaint_helper` exists in the module registry and `complaint_templates` is
seeded (migration 011), but:

- there is **no `/api/complaints*` route** and no `app/complaints/` package;
- there is **no `/complaint` route** in the SPA router (a click falls through
  to the catch-all redirect to `/`);
- it is filtered out of the worker nav and home page.

It is a planned module: draft a complaint from a template in the worker's
language, pre-fill it from a Contract Reader finding, and route it to the
right authority with India Labourline one tap away.

---

## 12. Translation subsystem

### Languages

Seven, everywhere in the schema and the `TargetLanguage` type: English (`en`,
canonical), Hindi (`hi`), Bengali (`bn`), Tamil (`ta`), Telugu (`te`),
Kannada (`kn`), Marathi (`mr`).

**What is actually translated at runtime today:** the Contract Reader's
Stage 3 output (clauses + overview), via Sarvam Mayura. The worker-facing
Contract Reader UI offers Hindi / Bengali / English as output languages.

**Content not yet translated:** Rights Guide fact cards and Schemes Finder
copy ship English-only in the database. The translation scripts exist
(`scripts/translate_rights_guide`, `scripts/translate_schemes`) but require
a run + native-speaker review before the rows go active. The app is honest
about this: non-English selections show an "in review" note and the English
canonical.

### Sarvam Mayura — `app/contracts/translate.py`

`POST https://api.sarvam.ai/translate`, model `mayura:v1`, with a
`mode` parameter (`formal` / `modern-colloquial` / `classic-colloquial` /
`code-mixed`) that the worker chooses. Retry policy: jittered exponential
backoff on `429` / `5xx` / transport errors, 3 attempts. Input is chunked to
stay under ~800 chars; a single oversize row degrades to per-field calls.

### Idiom library — `app/translate/idioms.py`

Mayura translates idioms literally ("at the end of the day" → a phrase about
the last hour of a shift). The idiom sandwich fixes that:

1. `substitute(text, target_language)` — an Aho-Corasick automaton (built
   once from `idiom_library`, cached at module level) scans the English
   source; each hit is replaced with an ASCII placeholder (`[[IDM_n]]`) that
   survives translation.
2. Caller sends the placeholder-laden text to Mayura.
3. `restore(translated, subs)` — swaps each placeholder for the pre-verified
   target-language equivalent from `idiom_translations`.

~75 idioms seeded (migration 007); the Idiom admin API lets a super-admin
grow the library and `reset_cache()` invalidates the automaton without a
restart. Placeholder namespaces (`[[IDM_n]]` vs `[[ROW_n]]`/`[[FLD]]`) don't
collide, so the idiom sandwich composes with the Stage 3 chunk packer.

### Transliteration

`target_script = "roman"` (native script → Latin letters) is in the schema
and the upload API but **not yet implemented** — the upload endpoint returns
`400` for it.

---

## 13. Retrieval / RAG

`app/retrieval/` powers Stage 2's grounded citations.

- **`embedder.py`** — OpenAI `text-embedding-3-large` at 1024 dimensions.
- **`chunker.py`** — splits statute text into retrieval chunks.
- **`retriever.py`** — `retrieve_context(query, source_type, k, threshold,
  tenant_id)` embeds the query and runs pgvector cosine-distance search over
  the `embeddings` table; `similarity = 1 - distance`; the threshold is a
  floor on similarity. `format_for_stage2(rows)` renders the hits into a
  prompt block that preserves source metadata so the annotator can cite what
  it saw. `NULL`-tenant rows are the shared corpus; a tenant caller also sees
  its own rows.

The statute corpus is seeded by migration 013 (Code on Social Security 2020,
Motor Vehicle Aggregator Guidelines, and related instruments).

---

## 14. Admin surfaces

Super-admin only (`is_super_admin`), under `/api/admin/*` and the `/admin`
SPA routes.

| Surface | API prefix | Purpose |
|---|---|---|
| **Users & access** | `/api/admin/users` | list users, edit flags, grant/revoke module access |
| **Modules** | `/api/admin/modules` | register/list module definitions |
| **Conversation Studio** | `/api/admin/conversation/*` | CRUD for the chat taxonomy — business units, issue types, data points, acknowledgment templates |
| **Idiom library** | `/api/admin/idioms` | CRUD for idioms and per-language equivalents |

Frontend: `AdminPage.tsx`, `ConversationStudioPage.tsx`, `IdiomsAdminPage.tsx`.

---

## 15. Frontend

### Stack & structure

React 19 + Vite 8 + TypeScript. Tailwind v4 for styling, shadcn/ui (Radix)
for primitives, `motion` for animation, `sonner` for toasts.

```
src/
├── main.tsx            React root + QueryClientProvider
├── router.tsx          createBrowserRouter — see routes below
├── stores/auth.ts      zustand (persisted): token, user, setSession, clearSession
├── lib/api.ts          shared axios instance + JWT interceptor + humaniseError
├── hooks/              one TanStack Query hook module per domain (useContracts, useRights, useSchemes, useModules, useAuth, …)
├── components/
│   ├── AppShell.tsx    authenticated layout (sidebar + scrollable content pane)
│   ├── AuthGuard.tsx   redirect to /login when unauthenticated
│   ├── ModuleGuard.tsx redirect home when the module isn't granted
│   ├── MainSidebar.tsx worker-ready module nav
│   └── ui/             shadcn components
└── pages/              one component per route
```

### Routes (`router.tsx`)

| Path | Component | Guard |
|---|---|---|
| `/login`, `/signup` | Login / Signup | redirect to `/` if already authed |
| `/` | HomePage | AuthGuard |
| `/contracts`, `/contracts/:id` | ContractReader / ContractDetail | AuthGuard + `contract_reader` |
| `/rights`, `/rights/:topicKey` | RightsGuide / RightsGuideDetail | AuthGuard + `rights_guide` |
| `/schemes`, `/schemes/:key` | SchemesFinder / SchemeDetail | AuthGuard + `schemes_finder` |
| `/chat/*` | — | redirect to `/` (chat disabled) |
| `/admin`, `/admin/conversation`, `/admin/idioms` | Admin surfaces | AuthGuard + super-admin |
| `*` | — | redirect to `/` |

Login and signup land the user on `/` (the module home), not the chat.

### Data fetching

TanStack Query throughout. Contract list/detail hooks poll every 2 s while any
row is non-terminal and stop when everything settles. Mutations invalidate the
relevant query keys.

### Build & serve

`npm run build` → `dist/`, copied into the nginx image (`nginx:1.27-alpine`).
`nginx.conf` is copied to `/etc/nginx/templates/default.conf.template` and
nginx's entrypoint runs `envsubst` on it at container start, so
`proxy_pass ${API_UPSTREAM}` is resolved at runtime — `http://app:8000` under
compose, the `sreshtha-api` Cloud Run URL in production. It does SPA-fallback
routing (`try_files … /index.html`) and reverse-proxies `/api`, `/auth`,
`/run`, `/ping` to the upstream with a 300 s read timeout (long enough for a
contract read), a 20 MB body cap, and `Host $proxy_host`
(`frontend/proxy_params.conf` — see §18 for why not `$host`).

---

## 16. Observability & logging

- The `app.*` logger tree has its own stdout handler at `INFO`, configured in
  `app/main.py` (`_configure_app_logging`) and **re-asserted after
  `bootstrap.run()`** — Alembic's `env.py` calls
  `logging.config.fileConfig()`, which otherwise disables every existing
  logger and drops the root level to `WARN`. `alembic/env.py` also passes
  `disable_existing_loggers=False`.
- Result: pipeline diagnostics (`get_provider: routing to OpenAI`,
  `stage 3 source breakdown: {…}`, `contract <id>: translate check: …`) and
  uvicorn access logs both reach `docker logs`.
- Contract processing failures are logged with `logger.exception` and the
  contract is marked `failed` with a plain worker-facing message.
- `/score` and `/simulator/healthz` (legacy eval endpoints) are auth-guarded:
  anonymous → `401`; an unreachable simulator → `502` (not a raw `500`).

---

## 17. Testing

```bash
pytest                        # backend — 210 tests
cd frontend && npm run lint   # oxlint (warnings only)
cd frontend && npm run build  # type-check + production build
```

`tests/` (pytest, `asyncio_mode = auto`, FastAPI `TestClient`):

| Area | Files |
|---|---|
| Auth | `test_auth_routes.py` |
| Modules / access | `test_conversation_admin_routes.py`, `test_idioms_admin_routes.py` |
| Sessions | `test_sessions_routes.py`, `test_chatbot_availability.py` |
| Contract Reader — routes | `test_contracts_routes.py` (upload validation incl. `.txt`/`.docx` accept + spoof rejection, ownership 404, consent gating) |
| Contract Reader — extraction | `test_contract_extraction.py` (txt encodings, `.docx` run/entity handling, zip rejection, Tesseract language routing, real image OCR when the binary is present) |
| Contract Reader — Stage 2/3 | `test_contract_stage3_failure.py`, `test_contract_jurisdiction_guards.py`, `test_stage2_validator.py` |
| Chat starters | `test_chat_starters_routes.py` |

The suite exercises route plumbing, validation, ownership, seeded content, the
Stage 2 override matrix, jurisdiction guards, and text extraction. It does
**not** hit OpenAI/Sarvam — the full end-to-end LLM pipeline is verified
manually against a running stack.

---

> **The authoritative deployment guide is
> [`CLOUD_RUN_DEPLOYMENT.md`](CLOUD_RUN_DEPLOYMENT.md)** — exact commands,
> secrets, migrations, nginx, troubleshooting, and rollback. This section is
> a summary; that document wins on any conflict.

### Local / self-host — `docker-compose.yml`

`docker compose up --build` (see §4). Three containers: `postgres`
(pgvector), `app` (uvicorn), `frontend` (nginx). `FRONTEND_PORT` moves the SPA
off `5173`; `API_UPSTREAM` is set to `http://app:8000` for the compose
network (the same nginx template is used in production with the Cloud Run API
URL).

### Production — Cloud Run (manual)

Two services in project `gen-lang-client-0368265372`, region `asia-south1`:

| Service | Image | Port | Backing |
|---|---|---|---|
| `sreshtha-api` | `…/sreshtha/api:<git-sha>` — built from the **root `Dockerfile`** | 8000 | Cloud SQL `sreshtha-db`, Secret Manager, Cloud Storage `…-sreshtha-contracts` |
| `sreshtha-web` | `…/sreshtha/web:<git-sha>` — built from `frontend/Dockerfile` | 80 | proxies `/api`,`/auth`,`/run`,`/ping` to `API_UPSTREAM` (the api service URL) |

- **Deployment is manual and intentionally so.** `origin/main` is the
  production source of truth. The deployment owner pulls `main`, tags the
  image with `git rev-parse --short HEAD`, `docker build --platform
  linux/amd64`, pushes to Artifact Registry (`sreshtha` repo), and
  `gcloud run deploy`s the changed service. No GitHub Actions, no Cloud Build
  trigger — `cloudbuild.yaml` is legacy and not part of this path.
- **The API image must use the root `Dockerfile`, not `Dockerfile.cloudrun`.**
  The root image ships `/app/alembic` + `/app/alembic.ini`; the container runs
  `alembic upgrade head` on startup. An image without the migration files
  starts against an empty schema.
- Secrets (`DATABASE_URL`, `JWT_SECRET`, `OPENAI_API_KEY`, `SARVAM_API_KEY`)
  are injected from Secret Manager via `--set-secrets`, never as literals.
- The runtime service account is
  `sreshtha-run@gen-lang-client-0368265372.iam.gserviceaccount.com` (Cloud
  SQL, Secret Manager, Artifact Registry, Cloud Storage, Vertex AI, Logging).
- **nginx `Host` header:** `frontend/proxy_params.conf` uses
  `proxy_set_header Host $proxy_host` (not `$host`). On Cloud Run `$host`
  makes the frontend proxy back to itself → recursive proxying and
  "Request Header Or Cookie Too Large". Do not change this.
- `/ping` is the liveness endpoint on both services (named `/ping`, not
  `/healthz`, because Cloud Run's frontend intercepts `/healthz`, `/health`,
  `/livez`).
- Rollback = `gcloud run services update-traffic <service>
  --to-revisions=<known-good>=100`.

### Image notes

The production API image (`Dockerfile`) is ~480 MB: Python 3.11-slim +
tesseract + Indic traineddata + `pip install .`, no torch/CUDA. Dropping the
EasyOCR/torch stack took it from ~1.5 GB and removed the ~285 MB
first-request model download.

---

## 19. Known limitations & roadmap

| Area | Status |
|---|---|
| **Rights Guide / Schemes translations** | English-only in the shipped DB. Scripts exist; need a run + native-speaker review before rows go active. |
| **Photo OCR quality** | Tesseract handles clean scans and photos well; low-quality phone photos (skew, shadow, glare) still need an image-preprocessing pass (deskew, adaptive threshold) — a near-term hardening item. A cloud-vision fallback for rare scripts is on the roadmap. |
| **Roman-script output** (`target_script=roman`) | In the schema and API; not implemented (returns 400). |
| **Stage 2 citation precision** | Citations are grounded in the RAG corpus but "View source" links sometimes resolve to a ministry homepage rather than a specific provision, and instrument names can be imprecise. Corpus/prompt tuning. |
| **Chatbot Sahaayak** | Disabled. Needs its taxonomy, prompts, and safety rules rewritten for worker rights. |
| **Complaint Helper** | Planned. Templates seeded; no route or API yet. |
| **Legacy cruft** | The QuickBites tables (`orders`, `riders`, …) and `/run/*`, `/score`, `/simulator/*` endpoints remain from the original support-bot codebase. Auth-guarded but not part of the product. |
| **Voice input / TTS** | `fact_cards.audio_url` and Sarvam ASR/TTS are on the roadmap; not built. |
| **Async DB** | SQLAlchemy sessions are synchronous; contract processing runs in a `BackgroundTask` thread. Fine at current scale. |

---

## 20. Recent changes

The `contract-formats-and-gap-fixes` branch (September 2026):

**Contract Reader**
- Accept `.txt` and `.docx` uploads (text formats and born-digital PDFs skip
  OCR entirely).
- Replace EasyOCR/PyTorch with **Tesseract** — real extraction on ARM,
  ~1 GB smaller image, no runtime model download.
- `source_language="en"` now uses an English-only OCR reader instead of
  always loading Devanagari (which corrupted Latin text).
- Stage 3 rewrite follows `LLM_PROVIDER` instead of being pinned to Vertex
  (which made every rewrite fail on the default OpenAI path).
- Translate the Stage 3 **overview** (`top_summary` + `top_actions`), not
  just the per-clause cards.
- MIME validation recovers the real type from the filename extension for
  generic content types; consent copy names the configured providers.

**Chatbot**
- Disabled behind `CHATBOT_ENABLED` (default off); endpoints `503`; removed
  from nav / home / default grants / `/chat` route.
- Login and signup land on `/` instead of the retired `/chat`.

**Platform**
- Logging: fixed Alembic's `fileConfig()` disabling every app logger during
  bootstrap — INFO pipeline diagnostics and access logs now reach stdout.
- `/score` and `/simulator/healthz` auth-guarded (clean `401` / `502`).
- Dropped `torch` / `torchvision` / `easyocr` from `pyproject.toml` and both
  Dockerfiles.

**Docs** — README, `DESIGN.md`, `PRD.md` updated for Tesseract and the new
formats.

**Tests** — +20 (contract extraction unit tests, `.txt`/`.docx` route
accept/reject, chatbot-availability guard). 210 passing.

---

## Not legal advice

Sreshtha delivers information, not legal advice. For formal help, workers can
call **India Labourline** at **1800-419-1550**. Every module carries this
disclaimer.
