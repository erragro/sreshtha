from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# pydantic-settings' env_file= below loads .env into this Settings object,
# but Google's auth library reads GOOGLE_APPLICATION_CREDENTIALS straight
# from os.environ, bypassing our Settings entirely — so .env has to also be
# loaded into the real process environment, not just parsed by pydantic.
load_dotenv(PROJECT_ROOT / ".env")
DATA_TODAY = date(2026, 4, 13)
POLICY_FAQ_PATH = PROJECT_ROOT / "policy_and_faq.md"
SQLITE_SEED_PATH = PROJECT_ROOT / "data" / "app.db"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://sreshtha:sreshtha@localhost:5432/sreshtha"

    # Logical model roles; each provider maps them to a concrete model id.
    model_fast: str = "fast"      # used by Stage 0 classifier
    model_smart: str = "smart"    # used by Stage 1 evaluator + Stage 3 responder

    # Reasoning provider defaults to OpenAI. Vertex AI (Gemini) is the
    # explicit fallback for local testing until Contract Reader is
    # iron-clad on one provider; production swap is deferred.
    # Google AI Studio bare-key access has been removed — Vertex is
    # the only Google path (needs GOOGLE_CLOUD_PROJECT + ADC via
    # `gcloud auth application-default login`).

    # Vertex AI (Gemini) — backup reasoning path. Auth via ADC only.
    google_cloud_project: str = ""
    google_cloud_location: str = "asia-south1"
    gemini_fast_model: str = "gemini-2.5-flash-lite"
    gemini_smart_model: str = "gemini-2.5-flash"

    # Sarvam AI (all other Indian languages). Model naming as of 2026-08:
    # sarvam-105b is the reasoning model (emits reasoning_content and eats
    # into max_tokens); sarvam-105b-conversations is the non-thinking
    # variant that returns directly. Default to conversations for both
    # roles because Sarvam's starter tier caps completion tokens at 4096
    # and the reasoning burns most of that on internal chain-of-thought.
    sarvam_api_key: str = ""
    sarvam_fast_model: str = "sarvam-105b-conversations"
    sarvam_smart_model: str = "sarvam-105b-conversations"
    # Ceiling for max_tokens in Sarvam requests. Starter subscription cap
    # is 4096; requests above this get rejected with a 400. The provider
    # clamps every call to this ceiling so callers can pass their own
    # ideal budget without knowing the subscription tier.
    sarvam_max_tokens_cap: int = 4096

    # OpenAI — default reasoning provider for Contract Reader stages
    # 1-3 and the Cardinal chat pipeline.
    openai_api_key: str = ""
    openai_fast_model: str = "gpt-4o-mini"
    openai_smart_model: str = "gpt-4o"
    openai_base_url: str = "https://api.openai.com/v1"

    # Provider selection for the reasoning stack (Stage 1 / Stage 2 /
    # Stage 3 in ``app/contracts``). One of:
    #   ""        — default: OpenAI
    #   "openai"  — explicit OpenAI (same as default)
    #   "vertex"  — Gemini via Vertex AI (requires GOOGLE_CLOUD_PROJECT + ADC)
    llm_provider: str = ""

    # Google Cloud Translation API v2 (Basic) — language detection only
    google_translate_api_key: str = ""

    simulator_base_url: str = "http://localhost:8000"
    candidate_token: str = "demo"

    refund_soft_cap_inr: int = 1500
    confidence_floor: float = 0.6
    dedup_ttl_seconds: int = 600

    # -- Auth ----------------------------------------------------------------
    # JWT secret MUST be overridden in every environment via env var. The
    # default value here is a marker string; app boot refuses to run with it
    # in prod (see main.py startup guard).
    jwt_secret: str = "CHANGE_ME_IN_PRODUCTION_this_default_is_unsafe"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 60 * 24        # 24h — matches session UX
    jwt_issuer: str = "sreshtha"
    password_min_length: int = 8
    # slowapi limits — string form because slowapi parses these
    auth_signup_rate: str = "10/hour"
    auth_login_rate: str = "30/hour"

    # Super-admin bootstrap. If set, the first signup that matches this
    # email becomes super_admin. If not set, the very first user to sign
    # up becomes super_admin (single-tenant / demo mode).
    super_admin_email: str = ""

    # Newly signed-up users get 'view' access to these module keys by
    # default so the demo works out of the box. Comma-separated env var.
    default_module_keys: str = "chatbot,contract_reader,rights_guide,schemes_finder,complaint_helper"

    # -- Contract Reader storage --------------------------------------------
    # Where uploaded contract files live. Local dev writes to a repo-relative
    # path; prod (Cloud Run) overrides via env var to a GCS bucket path.
    # See app/contracts/storage.py — LocalStorage prefixes this root, GCS
    # variant treats it as bucket name + prefix.
    contract_storage_root: str = "./data/contracts"
    contract_max_bytes: int = 10 * 1024 * 1024  # 10 MB

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
