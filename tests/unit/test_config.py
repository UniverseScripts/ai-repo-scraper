import pytest
import sys
import importlib
from core.config import settings

def test_settings_dynamic_monkeypatch(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test_dynamic_token_123")
    assert settings.GITHUB_TOKEN == "test_dynamic_token_123"

def test_missing_resend_api_key_raises_runtime_error(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://mock")
    monkeypatch.setenv("REDIS_URL", "redis://mock")
    
    # Clear api.main from sys.modules to force a fresh module execution
    sys.modules.pop("api.main", None)
    
    # Assert that importing api.main directly executes its startup guard and raises RuntimeError
    with pytest.raises(RuntimeError, match="CRITICAL: RESEND_API_KEY environment variable missing"):
        importlib.import_module("api.main")

def test_missing_resend_from_email_raises_runtime_error(monkeypatch):
    """Without a verified sender, Resend rejects every dispatch and no subscriber
    receives a key. This must fail at boot, not silently at the first payment."""
    monkeypatch.setenv("RESEND_API_KEY", "mock_resend_key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://mock")
    monkeypatch.setenv("REDIS_URL", "redis://mock")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "")

    sys.modules.pop("api.main", None)

    with pytest.raises(RuntimeError, match="CRITICAL: RESEND_FROM_EMAIL environment variable missing"):
        importlib.import_module("api.main")

def test_missing_api_key_signing_secret_raises_runtime_error(monkeypatch):
    """Key derivation is deterministic on this secret; without it the webhook cannot
    issue a credential at all."""
    monkeypatch.setenv("RESEND_API_KEY", "mock_resend_key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://mock")
    monkeypatch.setenv("REDIS_URL", "redis://mock")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "keys@mock-agentrisk.test")
    monkeypatch.setenv("API_KEY_SIGNING_SECRET", "")

    sys.modules.pop("api.main", None)

    with pytest.raises(RuntimeError, match="CRITICAL: API_KEY_SIGNING_SECRET environment variable missing"):
        importlib.import_module("api.main")
