import pytest
import asyncio
from fastapi import status
from unittest.mock import patch, AsyncMock
from db.models import PackageRiskMetric
from api.service import RegistryNotFound, UntrackablePackage, UpstreamRateLimited

@pytest.mark.asyncio
async def test_history_route_registered_before_package_risk(async_client, async_session, valid_api_key):
    """
    Verifies Route Ordering (Fix A):
    GET /api/v1/package-risk/npm/react/history MUST route to history handler,
    returning a list of records, and NOT get swallowed by greedy {package_name:path}.
    """
    raw_key, api_key_model = valid_api_key

    # Seed 2 historical metrics for npm/react
    metric1 = PackageRiskMetric(
        package_name="npm/react",
        commit_velocity_24h=100,
        open_issues_delta=0,
        fork_velocity_24h=10,
        contributor_churn=0.5,
        maintainer_count=1,
        single_maintainer_flag=True
    )
    async_session.add(metric1)
    await async_session.commit()

    response = await async_client.get(
        "/api/v1/package-risk/npm/react/history",
        headers={"X-API-Key": raw_key}
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["package_name"] == "npm/react"
    assert "maintainer_concentration_index" in data[0]

@pytest.mark.asyncio
async def test_ecosystem_scoped_typosquatting(async_client, async_session, valid_api_key):
    """
    Verifies Ecosystem-Scoped Typosquatting (Fix B):
    Querying non-existent 'npm/reaact' when 'npm/react' is in DB returns HTTP 404
    with possible_typosquat_of: 'npm/react' and similarity >= 0.80.
    """
    raw_key, api_key_model = valid_api_key

    # Seed known real package npm/react
    metric = PackageRiskMetric(package_name="npm/react")
    async_session.add(metric)
    await async_session.commit()

    # Mock resolve_and_fetch_package_metrics to raise RegistryNotFound
    with patch("api.main.resolve_and_fetch_package_metrics", side_effect=RegistryNotFound("Not in npm")):
        response = await async_client.get(
            "/api/v1/package-risk/npm/reaact",
            headers={"X-API-Key": raw_key}
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert data.get("status") == "not_found"
    assert data.get("possible_typosquat_of") == "npm/react"
    assert data.get("similarity") >= 0.80

@pytest.mark.asyncio
async def test_scoped_npm_package_lazy_fetch(async_client, valid_api_key):
    """
    Verifies Scoped NPM Package Parsing (Fix C):
    Package 'npm/@modelcontextprotocol/sdk' splits correctly on first slash.
    """
    raw_key, api_key_model = valid_api_key

    from datetime import datetime, timezone

    mock_metric = PackageRiskMetric(
        package_name="npm/@modelcontextprotocol/sdk",
        timestamp=datetime.now(timezone.utc),
        commit_velocity_24h=50,
        open_issues_delta=0,
        fork_velocity_24h=5,
        contributor_churn=0.2,
        maintainer_count=2,
        single_maintainer_flag=False
    )

    with patch("api.main.resolve_and_fetch_package_metrics", return_value=mock_metric) as mock_fetch:
        response = await async_client.get(
            "/api/v1/package-risk/npm/@modelcontextprotocol/sdk",
            headers={"X-API-Key": raw_key}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["package_name"] == "npm/@modelcontextprotocol/sdk"
        mock_fetch.assert_called_once_with("npm/@modelcontextprotocol/sdk")

@pytest.mark.asyncio
async def test_on_demand_fetch_timeout_backpressure(async_client, valid_api_key):
    """
    Verifies 5s Timeout & Backpressure:
    A slow upstream live fetch (>5s) catches asyncio.TimeoutError and returns HTTP 504.
    """
    raw_key, api_key_model = valid_api_key

    async def slow_fetch(*args, **kwargs):
        await asyncio.sleep(10.0)

    with patch("api.main.resolve_and_fetch_package_metrics", side_effect=slow_fetch):
        response = await async_client.get(
            "/api/v1/package-risk/npm/unscanned-package-slow",
            headers={"X-API-Key": raw_key}
        )

    assert response.status_code == status.HTTP_504_GATEWAY_TIMEOUT
    data = response.json()
    assert "Resolution timeout" in data["detail"]

@pytest.mark.asyncio
async def test_missing_github_token_returns_503(async_client, valid_api_key, monkeypatch):
    """
    A missing server-side GitHub credential is OUR configuration fault, not evidence
    that the customer's package is untrackable. This previously surfaced as a false
    HTTP 404 claiming the package had no public GitHub repository.

    Deliberately unmocked: the guard must fire before any network call is attempted.
    """
    raw_key, _ = valid_api_key
    monkeypatch.setenv("GITHUB_TOKEN", "")

    response = await async_client.get(
        "/api/v1/package-risk/npm/some-unscanned-package",
        headers={"X-API-Key": raw_key}
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "credential not configured" in response.json()["detail"]

@pytest.mark.asyncio
async def test_github_rate_limited_returns_503(async_client, valid_api_key):
    """
    Budget exhaustion is transient and ours. It must not be reported as the package
    being untrackable — different failure, different remedy, different HTTP class.
    """
    raw_key, _ = valid_api_key

    with patch(
        "api.main.resolve_and_fetch_package_metrics",
        side_effect=UpstreamRateLimited("GitHub telemetry budget temporarily depleted. Retry shortly."),
    ):
        response = await async_client.get(
            "/api/v1/package-risk/npm/some-unscanned-package",
            headers={"X-API-Key": raw_key}
        )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "budget" in response.json()["detail"].lower()
