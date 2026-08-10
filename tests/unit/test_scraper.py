import pytest
from unittest.mock import AsyncMock, patch
from scraper.github_velocity import fetch_pypi_metrics, fetch_npm_metrics

@pytest.mark.asyncio
async def test_pypi_maintainer_count_none():
    mock_client = AsyncMock()
    mock_client.get.return_value.status_code = 200
    mock_client.get.return_value.json = lambda: {
        "info": {
            "maintainer_email": "test@example.com"
        },
        "releases": {}
    }

    result = await fetch_pypi_metrics(mock_client, "langchain")
    
    assert result.get("maintainer_count") is None

@pytest.mark.asyncio
async def test_npm_maintainer_count_valid():
    mock_client = AsyncMock()
    mock_client.get.return_value.status_code = 200
    mock_client.get.return_value.json = lambda: {
        "maintainers": [
            {"email": "test1@example.com"},
            {"email": "test2@example.com"}
        ],
        "time": {}
    }

    result = await fetch_npm_metrics(mock_client, "langchain")

    assert result.get("maintainer_count") == 2

@pytest.mark.asyncio
async def test_npm_maintainer_count_absent_is_none():
    """
    Absent maintainer metadata must yield None, not a substituted 1. Substituting 1
    set single_maintainer_flag and produced a fabricated MCI of 10.0 — maximum risk —
    out of missing data, which is the exact pattern Section 8 permanently prohibits.
    """
    mock_client = AsyncMock()
    mock_client.get.return_value.status_code = 200
    mock_client.get.return_value.json = lambda: {
        "maintainers": [],
        "time": {}
    }

    result = await fetch_npm_metrics(mock_client, "ghost-package")

    assert result.get("maintainer_count") is None
