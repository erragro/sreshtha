# Sreshtha — Technical Design

**Status:** working build; public-launch hardening remains
**Updated:** 2026-09-05

Sreshtha is a mobile-first platform for Indian gig workers. It explains
uploaded contracts, publishes rights information, and matches workers to
welfare schemes. This document is the technical reference for the current
repository; product policy and acceptance criteria are in [PRD.md](PRD.md).

## 1. System architecture

```text
React 19 + Vite client
        |
        | authenticated JSON / multipart API
        v
FastAPI application
        |-- auth, module access, and administration
        |-- Contract Reader, Rights Guide, Schemes Finder
        |-- chat/session substrate (Sahaayak retargeting in progress)
        |
        +------------------------------+
        |                              |
        v                              v
PostgreSQL 16 + pgvector         Contract object storage
Alembic migrations               local disk or Google Cloud Storage
        |
        v
AI providers, after recorded consent
  OpenAI: contract extraction and research
  Vertex AI: worker-facing English rendition
  Sarvam Mayura: Indic-language translation
```

| Path | Responsibility |
|---|---|
| `app/` | FastAPI routes, services, ORM models, policies, AI integrations |
| `app/contracts/` | Upload, storage, OCR, processing, analysis, translation |
| `app/rights/`, `app/schemes/` | Rights Guide and Schemes Finder APIs |
| `app/translate/idioms.py` | Idiom-preserving translation layer |
| `app/l1_cardinal/`, `app/l2_agents/` | Chat substrate being retargeted for Sahaayak |
| `frontend/` | React, TypeScript, Vite, Tailwind worker/admin interfaces |
| `alembic/versions/` | Database and content migrations `001` through `016` |
| `scripts/` | Tenant bootstrap, corpus ingestion, translation helpers |

## 2. Core platform — built

- **Backend:** FastAPI registers authentication, session/chat, contracts,
  rights, schemes, idiom-admin, module-access, and administration routers.
- **Frontend:** React 19 + TypeScript + Vite 8 + Tailwind v4. Routes are
  protected by authentication and module-access guards.
- **Data:** PostgreSQL 16 with `pgvector`, SQLAlchemy 2, and Alembic.
- **Auth:** email/password signup/login, bcrypt, JWT bearer tokens, rate
  limiting, and a production guard against the default JWT secret.
- **Access control:** module-level grants, super-admin functions, and tenant /
  tenant-membership schema for partner deployments.

## 3. Contract Reader — built

Contract Reader is the most complete worker-facing module. Its APIs are
authenticated and every record is user-scoped.

### 3.1 Processing flow

```text
PDF / JPEG / PNG upload
  -> validate size, declared type, and file signature
  -> save original + create uploaded_contracts record
  -> require recorded processing consent
  -> extract embedded PDF text or run local OCR
  -> Stage 1: metadata, contract type, and clauses
  -> Stage 2: operational risk and statute-aware annotations
  -> Stage 3: plain-language English explanation and actions
  -> Sarvam translation for selected worker-output language
  -> persist progressive output and mark ready
```

| Area | Implementation |
|---|---|
| File handling | PDF, JPEG, PNG; configured 10 MB ceiling; MIME signature checks; source-language hint |
| Storage | `LocalStorage` for development; `GCSStorage` when the configured root is `gs://...` |
| OCR | PyMuPDF embedded-text extraction before EasyOCR fallback; PDF/raster resource limits |
| Stage 1 | OpenAI `gpt-4o-mini` structured extraction of clauses and metadata |
| Stage 2 | OpenAI `gpt-4o` and pgvector retrieval of curated statutes; jurisdiction guard removes mismatched state-law citations |
| Stage 3 | Vertex AI Gemini English rendition, clause-rule library, deterministic validator, safe fallback |
| Translation | Sarvam Mayura chunked translation; per-row English fallback if translation fails |
| Idioms | Aho-Corasick substitution before Mayura and vetted restoration after; accepts `[[IDM_n]]` and `[IDM_n]` markers |
| Status | `uploaded -> ocr_pending -> ocr_done -> processing -> ready`, plus `failed` |

### 3.2 Contract APIs

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/contracts` | Upload with source/target language, tone, and consent |
| `GET` | `/api/contracts` | List the current user's uploads |
| `GET` | `/api/contracts/{id}` | Read processing status and stage output |
| `POST` | `/api/contracts/{id}/process` | Start/retry processing; reserves work to prevent duplicates |
| `GET` | `/api/contracts/{id}/download` | Download original without exposing its storage key |
| `DELETE` | `/api/contracts/{id}` | Delete the caller's stored original and record |

### 3.3 Consent and data flow

- The original file remains in application-controlled storage.
- `processing_consent` must be recorded before analysis can start.
- After consent, extracted text and derived clauses go to configured OpenAI,
  Vertex AI, and Sarvam services as required by each pipeline stage.
- The upload UI states this processing plainly; consent is not inferred from
  upload alone.

## 4. Content and worker modules — built

### Rights Guide

The API and frontend render statute-cited fact cards. Current canonical topics
are minimum wage, injury at work, grievance escalation, e-Shram registration,
and contract fairness. Content and translations are separate records, which
supports explicit English fallback where a reviewed translation is unavailable.

### Schemes Finder

Scheme matching is deterministic rather than LLM-driven. A worker profile
(state, occupation, demographics, and related details) is evaluated against
structured eligibility rules. The UI displays matches, supporting documents,
application links, and translated detail where available.

### Idiom library and administration

`idiom_library` and `idiom_translations` store vetted equivalents. The runtime
builds a cached Aho-Corasick matcher for linear-time scans. Admin UI/API
manages entries, translations, and cache invalidation. Other super-admin
surfaces manage users, module access, and conversation content.

### Retrieval and clause rules

- `embeddings` stores chunked statute material as 1024-dimension vectors.
- `app/retrieval/` chunks, embeds, and retrieves statute material for Stage 2.
- `clause_rules` holds constraints for common contract patterns. Stage 3
  classifies, generates under constraints, validates, retries once, then uses
  a safe fallback when necessary.

## 5. Frontend — built

| Route | Status |
|---|---|
| `/contracts`, `/contracts/:contractId` | Upload/list/detail, consent, source/output language controls, citations, overview, translation state, original download |
| `/rights`, `/rights/:topicKey` | Rights Guide list/detail |
| `/schemes`, `/schemes/:key` | Scheme matcher/detail |
| `/chat` | Existing chat shell; Sahaayak retargeting remains incomplete |
| `/admin`, `/admin/conversation`, `/admin/idioms` | Super-admin interfaces |

Contract Reader's public output selector is intentionally limited to Hindi,
Bengali, and English. Although the schema accepts other Indic languages, the
PRD does not make them a Contract Reader v1 public commitment.

## 6. Data model

| Migrations | Additions |
|---|---|
| `001-004` | Runtime/session schema, users, module access, conversation studio |
| `005-008` | Content models, contract language/script, idiom library, translation mode |
| `009-011` | Rights Guide, Schemes Finder, Complaint Helper content models/seeds |
| `012` | Tenants and tenant memberships |
| `013-015` | pgvector retrieval, clause-rule schema, seeded clause rules |
| `016` | `uploaded_contracts.processing_consent` |

Contract records include ownership, storage key, MIME type, source and target
language, translation mode, consent, OCR text, status, and staged JSON output.

## 7. Local development and deployment

- Python `>=3.11` (current local setup uses Python 3.13).
- Node.js 20+ for the frontend.
- Docker Compose provides PostgreSQL/pgvector; Alembic applies schema and
  content migrations; Uvicorn serves the API; Vite serves the UI.
- `Dockerfile.cloudrun` and `cloudbuild.yaml` build/publish a Cloud Run image.
- `cloudrun-entrypoint.sh` supports external `DATABASE_URL` for persistent
  PostgreSQL; `GCSStorage` supports a contract bucket.

Detailed setup commands and environment variables are in [README.md](../README.md).

## 8. Verification

Recent local validation completed:

- 182 backend tests passed in the full pytest suite.
- Vite production build completed successfully.
- A 20-page PDF completed the full Contract Reader pipeline in English,
  Hindi, Bengali, and Tamil test modes, with no provider errors or leaked
  idiom marker.

The Vite build emits a non-failing advisory for a JavaScript chunk larger than
the default 500 kB threshold.

## 9. Planned work

| Area | Planned work |
|---|---|
| Worker localisation | Persisted worker locale, reviewed Hindi/Bengali/English UI catalogs, localized backend-error mapping, explicit content fallback |
| Contract Reader UX | Mobile-first refactor, richer progress display, Rights Guide links from `topic_hint` |
| Content quality | Native-speaker and labour-law review gates for cards, translations, and clause rules |
| Complaint Helper | Service, API, frontend, copy/share/PDF workflow over existing templates |
| Authentication | OTP-first onboarding, recovery PIN, optional email, vault export |
| Deployment | Cloud Run, managed PostgreSQL, GCS, Secret Manager, observability, load testing |
| Chatbot | Retarget Cardinal as Sahaayak; add worker-document retrieval only with safety/disclosure complete |
| Voice and offline | Sarvam ASR/TTS with transcript confirmation; offline Rights Guide and contract reading |

Tamil, Telugu, Kannada, and Marathi Contract Reader output stay gated until
each language has at least 100 vetted idioms and native-speaker-reviewed
fact-card content.

## 10. Known limitations

- Contract jobs use FastAPI background tasks in the API process, not a durable
  external worker queue with independent retries and observability.
- Local file storage is unsuitable for multi-instance production; use GCS and
  persistent PostgreSQL in deployment.
- The app shell is not yet globally localized. Page-level language selectors
  do not replace the planned worker-locale system.
- Rights and scheme translations require native-speaker review before being
  represented as production-ready content.
- Sreshtha provides legal information and document comprehension, not legal
  representation or legal verdicts.

## 11. Related documents

| Document | Purpose |
|---|---|
| [PRD.md](PRD.md) | Product scope, language policy, quality gates, roadmap, non-goals |
| [TESTING_GUIDE.md](TESTING_GUIDE.md) | Test conventions |
| [RIGHTS_GUIDE_CONTENT_GUIDELINES.md](RIGHTS_GUIDE_CONTENT_GUIDELINES.md) | Content authoring and review |
