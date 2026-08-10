import httpx
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from db.connection import AsyncSessionLocal
from db.models import PackageRiskMetric
from core.config import settings
from scraper.github_velocity import (
    fetch_github_metrics,
    fetch_npm_metrics,
    fetch_pypi_metrics
)

class RegistryNotFound(Exception):
    """Raised when a package name does not exist in the npm or PyPI registry."""
    pass

class UntrackablePackage(Exception):
    """Raised when a package exists in registry but has no linked public GitHub repository."""
    pass

class UpstreamAuthUnavailable(Exception):
    """Raised when our GitHub credential is absent. A server-side configuration
    fault, not a statement about the package — must not surface as a 404."""
    pass

class UpstreamRateLimited(Exception):
    """Raised when the GitHub GraphQL budget is depleted. Transient and ours,
    not a statement about the package — must not surface as a 404."""
    pass

def extract_github_repo(url_val) -> str | None:
    """Helper to extract owner/repo string from various repository URL formats."""
    if not url_val:
        return None
    url_str = ""
    if isinstance(url_val, dict):
        url_str = url_val.get("url", "")
    elif isinstance(url_val, str):
        url_str = url_val

    if "github.com" not in url_str:
        return None

    # Clean git+https://, git://, .git
    clean = url_str.split("github.com/")[-1].replace(".git", "").strip("/")
    parts = clean.split("/")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return None

async def resolve_and_fetch_package_metrics(package_name: str) -> PackageRiskMetric:
    """
    On-demand telemetry fetcher.
    Splits package_name on first slash to support scoped npm packages (e.g. npm/@modelcontextprotocol/sdk).
    Queries registry for GitHub link, fetches live metrics, persists to PostgreSQL, and returns the entity.
    """
    parts = package_name.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid package_name format '{package_name}'. Expected 'ecosystem/name'.")

    ecosystem, raw_name = parts[0].lower(), parts[1]

    if ecosystem not in ("npm", "pypi"):
        raise ValueError(f"Unsupported ecosystem '{ecosystem}'. Supported: npm, pypi.")

    # GitHub's GraphQL API requires authentication outright. Without a token every
    # live fetch fails, and previously that was reported to the customer as an
    # untrackable package — a false statement about their package.
    if not settings.GITHUB_TOKEN:
        raise UpstreamAuthUnavailable(
            "GitHub telemetry unavailable: server credential not configured. "
            "This is a service-side fault, not a property of the requested package."
        )

    headers = {"Authorization": f"Bearer {settings.GITHUB_TOKEN}"}

    since_dt = datetime.now(timezone.utc) - timedelta(days=1)

    async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
        github_repo = None
        reg_result = {}

        if ecosystem == "npm":
            resp = await client.get(f"https://registry.npmjs.org/{raw_name}")
            if resp.status_code == 404:
                raise RegistryNotFound(f"Package '{package_name}' not found in npm registry.")
            if resp.status_code != 200:
                raise UntrackablePackage(f"npm registry query failed with HTTP {resp.status_code}.")

            data = resp.json()
            github_repo = extract_github_repo(data.get("repository"))
            reg_result = await fetch_npm_metrics(client, raw_name)

        elif ecosystem == "pypi":
            resp = await client.get(f"https://pypi.org/pypi/{raw_name}/json")
            if resp.status_code == 404:
                raise RegistryNotFound(f"Package '{package_name}' not found in PyPI registry.")
            if resp.status_code != 200:
                raise UntrackablePackage(f"PyPI registry query failed with HTTP {resp.status_code}.")

            data = resp.json()
            info = data.get("info", {})
            project_urls = info.get("project_urls") or {}

            # Search project_urls for GitHub link
            for k in ("Source", "Repository", "Code", "Homepage"):
                github_repo = extract_github_repo(project_urls.get(k))
                if github_repo:
                    break

            if not github_repo:
                github_repo = extract_github_repo(info.get("home_page"))

            reg_result = await fetch_pypi_metrics(client, raw_name)

        if not github_repo:
            raise UntrackablePackage(f"Package '{package_name}' exists in registry but has no associated public GitHub repository.")

        # These were previously collapsed into one UntrackablePackage -> HTTP 404.
        # They are different failures and the response must say which.
        gh_result = await fetch_github_metrics(client, github_repo, since_dt)
        if gh_result and gh_result.get("rate_limited"):
            raise UpstreamRateLimited(
                "GitHub telemetry budget temporarily depleted. Retry shortly; "
                "this is a service-side limit, not a property of the requested package."
            )
        if not gh_result:
            raise UntrackablePackage(
                f"GitHub repository '{github_repo}' could not be queried."
            )

        maintainer_count = reg_result.get("maintainer_count")

        payload = {
            "package_name": f"{ecosystem}/{raw_name}",
            "timestamp": datetime.now(timezone.utc),
            "commit_velocity_24h": gh_result.get("commit_velocity_24h", 0),
            "open_issues_delta": gh_result.get("open_issues_delta", 0),
            "fork_velocity_24h": gh_result.get("fork_velocity_24h", 0),
            "contributor_churn": gh_result.get("contributor_churn", 0.0),
            "maintainer_count": maintainer_count,
            "single_maintainer_flag": maintainer_count is not None and maintainer_count <= 1,
            "days_since_last_publish": reg_result.get("days_since_last_publish"),
            "publish_cadence_variance": reg_result.get("publish_cadence_variance"),
            "fork_spike_ratio": gh_result.get("fork_spike_ratio")
        }

    async with AsyncSessionLocal() as session:
        stmt = insert(PackageRiskMetric).values([payload])
        stmt = stmt.on_conflict_do_update(
            index_elements=['package_name', 'timestamp'],
            set_={
                'commit_velocity_24h': stmt.excluded.commit_velocity_24h,
                'open_issues_delta': stmt.excluded.open_issues_delta,
                'fork_velocity_24h': stmt.excluded.fork_velocity_24h,
                'contributor_churn': stmt.excluded.contributor_churn,
                'maintainer_count': stmt.excluded.maintainer_count,
                'single_maintainer_flag': stmt.excluded.single_maintainer_flag,
                'days_since_last_publish': stmt.excluded.days_since_last_publish,
                'publish_cadence_variance': stmt.excluded.publish_cadence_variance,
                'fork_spike_ratio': stmt.excluded.fork_spike_ratio
            }
        )
        await session.execute(stmt)
        await session.commit()

        # Retrieve inserted node
        res_stmt = select(PackageRiskMetric).where(
            PackageRiskMetric.package_name == f"{ecosystem}/{raw_name}"
        ).order_by(PackageRiskMetric.timestamp.desc()).limit(1)
        res = await session.execute(res_stmt)
        return res.scalars().first()
