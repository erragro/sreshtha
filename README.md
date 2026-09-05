# Sreshtha

**An app for India's gig workers.**

Contract explanations, rights guidance, and welfare access, in the
languages workers actually speak. Built on Google Gemini 2.5 Flash
(Vertex AI, `asia-south1`), Sarvam Mayura for Indic translation, and an
in-house Indic vision stack.

Blog: [erragro.github.io/sreshtha-blog](https://erragro.github.io/sreshtha-blog/) ·
License: [proprietary — all rights reserved](LICENSE), © 2026 Surajit Chaudhuri.

---

## Quickstart (Docker)

The full stack — Postgres + pgvector, FastAPI backend, and the Vite/React
frontend — runs from a single `docker compose up`.

```bash
git clone https://github.com/erragro/sreshtha.git
cd sreshtha
cp .env.example .env          # then fill in OPENAI_API_KEY + SARVAM_API_KEY
docker compose up --build
```

Once the three containers are healthy:

- Frontend: <http://localhost:5173>
- API:      <http://localhost:8000>
- Postgres: `localhost:5435` (user `sreshtha`, db `sreshtha`)

Alembic migrations (001–016) run automatically on backend startup — the first
boot seeds `clause_rules`, the statute corpus, and starter tenant data.

**Vertex AI (optional).** To use Gemini via Vertex instead of OpenAI, set
`LLM_PROVIDER=vertex` and `GOOGLE_CLOUD_PROJECT` in `.env`, then point
`GOOGLE_APPLICATION_CREDENTIALS_HOST` at the absolute path of a service-account
JSON key on your host. Docker Compose bind-mounts it into the container.

To reset the local database (drops all data):

```bash
docker compose down -v
```

---

## Modules

| Module            | Status | Backend                | Frontend                          |
|-------------------|--------|------------------------|-----------------------------------|
| Contract Reader   | Live   | `app/contracts/`       | `frontend/src/pages/Contract*`    |
| Rights Guide      | Live   | `app/rights/`          | `frontend/src/pages/RightsGuide*` |
| Schemes Finder    | Live   | `app/schemes/`         | `frontend/src/pages/Schemes*`     |
| Complaint Helper  | In flight | `app/complaints/`   | `frontend/src/pages/Complaint*`   |
| Chatbot Sahaayak  | Retargeting from the Cardinal chat pipeline | `app/l1_cardinal/`, `app/l2_agents/`, `app/sessions/`, `app/chat/` | `frontend/src/pages/ChatPage.tsx` |

Every module speaks seven Indic languages (Hindi, Bengali, Tamil,
Telugu, Kannada, Marathi, English) with four tone modes on
worker-facing surfaces.

## Repository layout

```
sreshtha/
├── app/                          FastAPI backend
│   ├── auth/                     Users, JWT, password hashing
│   ├── contracts/                Contract Reader — OCR + 3-stage Gemini + Mayura
│   ├── rights/                   Rights Guide — fact-card API
│   ├── schemes/                  Schemes Finder — wizard + eligibility matcher
│   ├── complaints/               Complaint Helper — templates + render
│   ├── idioms/                   Idiom library admin
│   ├── translate/                Sarvam Mayura translation, idiom sandwich
│   ├── modules/                  Module registry + per-user ACL
│   ├── sessions/                 Chat session CRUD
│   ├── l1_cardinal/              5-phase chatbot pipeline (retargeting for Sahaayak)
│   ├── l2_agents/                Stage-2 evaluators (retargeting for Sahaayak)
│   ├── conversation_studio/      Admin surface for chat taxonomy + templates
│   ├── db.py, models.py          SQLAlchemy 2 async session + all ORM models
│   ├── main.py                   FastAPI app entrypoint
│   └── config.py                 Pydantic Settings — reads .env
├── alembic/versions/             Database migrations, ordered 001-012
├── frontend/                     React 19 + Vite + Tailwind v4 + shadcn/ui
├── scripts/                      One-shot helpers (bootstrap tenant, translation runs)
├── docs/                         PRD, design notes, content guidelines
└── tests/                        pytest suite
```

## The Contract Reader pipeline (anchor module)

```
worker upload → POST /api/contracts
        │
        ├─► app/contracts/service.py         validate + save + row insert
        ├─► app/contracts/storage.py         local disk (Cloud Storage on prod)
        ├─► app/contracts/processor.py       status machine + orchestration
        │       │
        │       ├─► app/contracts/ocr.py     EasyOCR per language, in-house
        │       ├─► app/contracts/stage1.py  Gemini · extract clauses      (English)
        │       ├─► app/contracts/stage2.py  Gemini · annotate + risk tier (English)
        │       ├─► app/contracts/stage3.py  Gemini · rewrite for worker   (English)
        │       └─► app/contracts/translate.py  Sarvam Mayura, chunked
        │              │
        │              ├─► app/translate/idioms.py   substitute BEFORE Mayura
        │              ├─► Mayura translation call
        │              └─► app/translate/idioms.py   restore AFTER
        │
        └─► worker view: GET /api/contracts/{id}  — worker's language + tone
```

## Runtime

**Backend.** Python 3.13, FastAPI, SQLAlchemy 2, Postgres 16, Alembic.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d postgres          # local Postgres on 5433
alembic upgrade head
uvicorn app.main:app --port 8000 --reload
```

**Frontend.** Node 20+, Vite 8, Tailwind v4.

```bash
cd frontend
npm install
npm run dev                            # http://localhost:5173
```

**Env.** Copy `.env.example` → `.env`, fill:

- `DATABASE_URL` — Postgres connection string
- One of:
  - `GEMINI_API_KEY` (Google AI Studio, fastest to iterate)
  - `GOOGLE_APPLICATION_CREDENTIALS` + `GOOGLE_CLOUD_PROJECT` (Vertex AI, production)
- `SARVAM_API_KEY` — for Sarvam Mayura translation
- `JWT_SECRET` — any random 256-bit string

## Content translation

Sreshtha's fact cards, scheme descriptions, and complaint templates ship
in English (canonical), then run through Sarvam Mayura for Hindi,
Bengali, and Tamil. Two idempotent scripts:

```bash
python -m scripts.translate_rights_guide         # 5 cards × 3 languages
python -m scripts.translate_schemes              # 10 schemes × 3 languages
```

Native-speaker review of translations is a separate step; the scripts
land translations at `is_active=true` so the app renders, but production
sign-off requires the checklist in
[docs/RIGHTS_GUIDE_CONTENT_GUIDELINES.md](docs/RIGHTS_GUIDE_CONTENT_GUIDELINES.md).

## Google tech stack

| In production | Where used |
|---------------|------------|
| Gemini 2.5 Flash | Contract Reader — all three reasoning stages, English only |
| Gemini 2.5 Flash Lite | Language detection, lighter classification |
| Vertex AI | Hosts both Gemini models (region `asia-south1`) |
| Google AI Studio | Alternate auth path for local dev |
| `google-genai` SDK v1.0+ | Python client |

| On the roadmap | Purpose |
|----------------|---------|
| Cloud Run | Production deploy of API + built frontend |
| Cloud Storage | Encrypted at-rest storage of uploaded contracts |
| Gemini Vision | Fallback OCR for low-quality photos in rare scripts |

## Multi-tenant deployment (for partners)

Sreshtha ships with tenant scaffolding so a welfare board, union,
sponsor, or NGO can run a self-hosted or shared deployment.

```bash
# After alembic upgrade head, bootstrap a new tenant + owner user:
python -m scripts.bootstrap_tenant \
    --slug karnataka-welfare \
    --name "Karnataka Platform Gig Workers Welfare Board" \
    --kind welfare_board \
    --admin-email owner@example.gov.in \
    --tagline "Powered by Sreshtha" \
    --primary-color "#5b3fd6"
```

Every content row carries a nullable `tenant_id`:

- `NULL` — shared library, visible to all tenants (the default seed).
- `<uuid>` — tenant-specific override or addition.

Users may belong to multiple tenants via `tenant_memberships`.

## Documentation

- [`docs/PRD.md`](docs/PRD.md) — product requirements + 20-day timeline
- [`docs/DESIGN.md`](docs/DESIGN.md) — architecture notes
- [`docs/RIGHTS_GUIDE_CONTENT_GUIDELINES.md`](docs/RIGHTS_GUIDE_CONTENT_GUIDELINES.md) — the 8 rules every fact card follows
- [`docs/RIGHTS_GUIDE_CONTENT_DRAFT.md`](docs/RIGHTS_GUIDE_CONTENT_DRAFT.md) — English canonical for the first 5 cards
- [`docs/TESTING_GUIDE.md`](docs/TESTING_GUIDE.md) — test conventions

## Testing

```bash
pytest                        # backend suite
cd frontend && npm run lint   # frontend lint
```

## License

Proprietary — [all rights reserved](LICENSE), © 2026 Surajit Chaudhuri.
The repository is public so that Google Meet the Builders (Gen AI
Academy APAC) judges can review the submission. Public availability
does not imply an open-source license.

For partnership, licensing, or research-use inquiries, contact the
copyright holder.

## Not legal advice

Sreshtha delivers information, not legal advice. For formal help,
workers can call India Labourline at **1800-419-1550**.
