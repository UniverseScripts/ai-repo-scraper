import pytest
from fastapi import status
from db.models import PackageRiskMetric, APIKey
from sqlalchemy import select
from db.connection import AsyncSessionLocal
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_get_package_risk_unauthorized(async_client):
    response = await async_client.get("/api/v1/package-risk/npm/react")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

@pytest.mark.asyncio
async def test_get_package_risk_authorized(async_client, async_session, valid_api_key):
    raw_key, api_key_model = valid_api_key
    
    metric = PackageRiskMetric(
        package_name="npm/react",
        commit_velocity_24h=142,
        open_issues_delta=-5,
        fork_velocity_24h=38,
        contributor_churn=0.824,
        maintainer_count=5,
        single_maintainer_flag=False,
        days_since_last_publish=10,
        publish_cadence_variance=2.5,
        fork_spike_ratio=1.2
    )
    async_session.add(metric)
    await async_session.commit()

    response = await async_client.get(
        "/api/v1/package-risk/npm/react",
        headers={"X-API-Key": raw_key}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["package_name"] == "npm/react"
    assert data["commit_velocity_24h"] == 142
    assert data["maintainer_count"] == 5

@pytest.mark.asyncio
@patch('api.main.httpx.AsyncClient')
async def test_lemon_squeezy_webhook_subscription(mock_client_class, async_client):
    import hmac
    import hashlib
    import json
    
    mock_instance = AsyncMock()
    mock_client_class.return_value.__aenter__.return_value = mock_instance
    mock_post = mock_instance.post
    mock_post.return_value.status_code = 200
    mock_post.return_value.raise_for_status = lambda: None
    
    secret = "mock_secret"
    payload = {
        "meta": {"event_name": "subscription_created"},
        "data": {"id": "sub_123", "attributes": {"user_email": "b2b_subscriber@enterprise.com", "variant_id": "mock_variant_id"}}
    }
    raw_body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    
    response = await async_client.post(
        "/webhooks/lemon-squeezy",
        content=raw_body,
        headers={"X-Signature": signature, "Content-Type": "application/json"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "success"
    assert response.json()["provisioned"] is True
    assert response.json()["key_dispatched"] is True
    
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.resend.com/emails"
    assert kwargs["json"]["to"] == ["b2b_subscriber@enterprise.com"]
    # Sender comes from configuration, never a hardcoded placeholder. The literal
    # "onboarding@yourdomain.com" would be rejected by Resend as an unverified domain.
    assert kwargs["json"]["from"] == "keys@mock-agentrisk.test"

@pytest.mark.asyncio
@patch('api.main.httpx.AsyncClient')
async def test_webhook_resend_failure_returns_500(mock_client_class, async_client, async_session):
    """
    A failed key dispatch must NOT return 2xx. Lemon Squeezy treats 2xx as delivered
    and never retries, which is precisely how a paying customer ends up with nothing.
    The key row must still be persisted so the retry converges on the same credential.
    """
    import hmac
    import hashlib
    import json

    mock_instance = AsyncMock()
    mock_client_class.return_value.__aenter__.return_value = mock_instance
    mock_post = mock_instance.post

    def raise_err():
        raise Exception("Resend API down")

    mock_post.return_value.raise_for_status = raise_err

    secret = "mock_secret"
    payload = {
        "meta": {"event_name": "subscription_created"},
        "data": {"id": "sub_456", "attributes": {"user_email": "fail@enterprise.com", "variant_id": "mock_variant_id"}}
    }
    raw_body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    response = await async_client.post(
        "/webhooks/lemon-squeezy",
        content=raw_body,
        headers={"X-Signature": signature, "Content-Type": "application/json"}
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "delivery failed" in response.json()["detail"]

    # The key must still be persisted, so the retry is idempotent rather than re-minting.
    res = await async_session.execute(select(APIKey).where(APIKey.subscription_id == "sub_456"))
    assert res.scalars().first() is not None


@pytest.mark.asyncio
@patch('api.main.httpx.AsyncClient')
async def test_webhook_retry_is_idempotent(mock_client_class, async_client, async_session):
    """
    A retried subscription_created must converge on ONE row carrying the SAME key.
    subscription_id is UNIQUE, so a blind insert would fail the constraint on retry;
    and only the SHA-256 digest is stored, so a randomly generated key could never
    be re-sent. Hence deterministic derivation from the subscription id.
    """
    import hmac
    import hashlib
    import json

    mock_instance = AsyncMock()
    mock_client_class.return_value.__aenter__.return_value = mock_instance
    mock_post = mock_instance.post
    mock_post.return_value.status_code = 200
    mock_post.return_value.raise_for_status = lambda: None

    secret = "mock_secret"
    payload = {
        "meta": {"event_name": "subscription_created"},
        "data": {"id": "sub_retry", "attributes": {"user_email": "retry@enterprise.com", "variant_id": "mock_variant_id"}}
    }
    raw_body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    headers = {"X-Signature": signature, "Content-Type": "application/json"}

    first = await async_client.post("/webhooks/lemon-squeezy", content=raw_body, headers=headers)
    second = await async_client.post("/webhooks/lemon-squeezy", content=raw_body, headers=headers)

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_200_OK

    # Exactly one row for this subscription, not a duplicate or a constraint error.
    res = await async_session.execute(select(APIKey).where(APIKey.subscription_id == "sub_retry"))
    rows = res.scalars().all()
    assert len(rows) == 1

    # Both dispatches carried the identical raw key.
    assert mock_post.call_count == 2
    first_html = mock_post.call_args_list[0].kwargs["json"]["html"]
    second_html = mock_post.call_args_list[1].kwargs["json"]["html"]
    assert first_html == second_html

    # And that delivered key actually authenticates against the stored hash.
    delivered_key = first_html.split("<strong>")[1].split("</strong>")[0]
    assert hashlib.sha256(delivered_key.encode("utf-8")).hexdigest() == rows[0].valid_api_keys


@pytest.mark.asyncio
async def test_webhook_subscription_cancellation_deactivates_key(async_client, async_session):
    import hmac
    import hashlib
    import json
    import uuid

    # 1. Create active API key directly
    sub_id = "sub_cancel_789"
    hashed_key = hashlib.sha256(b"fake_key").hexdigest()
    key_record = APIKey(
        valid_api_keys=hashed_key,
        subscription_id=sub_id,
        is_active=True
    )
    async_session.add(key_record)
    await async_session.commit()
    
    secret = "mock_secret"
    payload = {
        "meta": {"event_name": "subscription_cancelled"},
        "data": {"id": sub_id, "attributes": {"user_email": "cancel@enterprise.com", "variant_id": "mock_variant_id"}}
    }
    raw_body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    
    response = await async_client.post(
        "/webhooks/lemon-squeezy",
        content=raw_body,
        headers={"X-Signature": signature, "Content-Type": "application/json"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    # Check DB directly
    await async_session.refresh(key_record)
    assert key_record.is_active is False
