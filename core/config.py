import os
import sys
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure project root is in sys.path when imported across modules/scripts
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

class Settings(BaseSettings):
    """
    Centralized, typed Pydantic Settings configuration manager.
    Parses environment variables dynamically from environment or .env file.
    Default empty string fallbacks allow isolated script runs while application
    startup logic enforces strict fail-fast validation.
    """
    DATABASE_URL: str = ""
    REDIS_URL: str = ""
    GITHUB_TOKEN: str = ""
    RESEND_API_KEY: str = ""
    LEMON_SQUEEZY_WEBHOOK_SECRET: str = ""
    LEMON_SQUEEZY_VARIANT_ID: str = ""
    CACHE_TTL_HOURS: int = 6

    # Sender address for transactional key dispatch. Must be an address on a
    # Resend-verified domain; Resend rejects unverified senders outright.
    RESEND_FROM_EMAIL: str = ""

    # Dedicated secret used to derive raw API keys deterministically from the
    # subscription id, so a retried webhook regenerates the identical key.
    # Deliberately NOT LEMON_SQUEEZY_WEBHOOK_SECRET — signing material and key
    # material stay separate.
    API_KEY_SIGNING_SECRET: str = ""

    # GraphQL budget the scheduled scraper leaves untouched, reserved for
    # customer-facing on-demand fetches (PROJECT_CONTEXT.pdf: live requests
    # take priority over background pre-warming).
    GITHUB_RATELIMIT_RESERVE: int = 1000

    model_config = SettingsConfigDict(
        env_file=os.path.join(project_root, ".env") if os.path.exists(os.path.join(project_root, ".env")) else None,
        env_file_encoding="utf-8",
        extra="ignore"
    )

def get_settings() -> Settings:
    """Returns a fresh Settings instance dynamically reflecting live environment."""
    return Settings()

class SettingsProxy:
    """Dynamic proxy delegating attribute access to fresh get_settings() calls to support monkeypatching."""
    def __getattr__(self, name: str):
        return getattr(get_settings(), name)

settings = SettingsProxy()
