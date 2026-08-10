import os
import sys
import asyncio
import httpx
from datetime import datetime, timedelta, timezone
import json
import statistics

# Ensure project root is in sys.path for standalone script execution
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.connection import AsyncSessionLocal
from sqlalchemy.dialects.postgresql import insert
from db.models import PackageRiskMetric

GRAPHQL_URL = "https://api.github.com/graphql"

def calculate_variance(timestamps):
    if len(timestamps) < 2:
        return None
    timestamps = sorted(timestamps)
    gaps = [(timestamps[i] - timestamps[i-1]).total_seconds() / 86400.0 for i in range(1, len(timestamps))]
    if len(gaps) < 2:
        return 0.0
    return statistics.variance(gaps)

async def discover_target_packages(client: httpx.AsyncClient) -> list[dict]:
    """
    Dynamically discover AI agent/MCP packages from NPM registry across multiple search terms.
    Deduplicates by resolved GitHub repository to handle monorepos gracefully.
    """
    targets = []
    queries = ["mcp", "agent", "llm", "claude", "anthropic", "openai-agent"]
    
    for q in queries:
        try:
            response = await client.get(f"https://registry.npmjs.org/-/v1/search?text={q}&size=250")
            if response.status_code == 200:
                data = response.json()
                for obj in data.get("objects", []):
                    pkg = obj.get("package", {})
                    name = pkg.get("name")
                    links = pkg.get("links", {})
                    repo_url = links.get("repository", "")
                    
                    if "github.com/" in repo_url:
                        parts = repo_url.split("github.com/")[-1].split("/")
                        if len(parts) >= 2:
                            owner = parts[0]
                            repo = parts[1].replace(".git", "").strip("/")
                            targets.append({
                                "name": name,
                                "ecosystem": "npm",
                                "github": f"{owner}/{repo}"
                            })
        except Exception as e:
            print(f"WARNING: Dynamic npm discovery failed for query '{q}': {e}")
        
    pypi_pilots = [
        {"name": "langchain", "ecosystem": "pypi", "github": "langchain-ai/langchain"},
        {"name": "openai", "ecosystem": "pypi", "github": "openai/openai-python"},
        {"name": "vllm", "ecosystem": "pypi", "github": "vllm-project/vllm"}
    ]
    
    # Deduplicate by resolved GitHub repo & package key
    seen_repos = set()
    seen_keys = set()
    final_targets = []
    
    for t in targets + pypi_pilots:
        key = f"{t['ecosystem']}/{t['name']}"
        repo_key = t["github"].lower()
        if key not in seen_keys and repo_key not in seen_repos:
            seen_keys.add(key)
            seen_repos.add(repo_key)
            final_targets.append(t)

    # No silent caps: npm's search endpoint hard-caps `size` at 250 per query, so
    # state what the fan-out actually yielded rather than implying full coverage.
    print(f"DISCOVERY: {len(targets)} raw npm candidates across {len(queries)} queries "
          f"-> {len(final_targets)} unique targets after dedup by resolved GitHub repo.")
    return final_targets

async def fetch_github_metrics(client: httpx.AsyncClient, github_repo: str, since_dt: datetime, reserve: int = 0) -> dict | None:
    if not github_repo:
        return None
        
    owner, name = github_repo.split("/")
    since_iso = since_dt.isoformat()
    issue_closed_query = f"repo:{github_repo} is:issue closed:>={since_iso}"
    issue_opened_query = f"repo:{github_repo} is:issue created:>={since_iso}"

    query = """
    query ($owner: String!, $name: String!, $since: GitTimestamp!, $issueClosedQuery: String!, $issueOpenedQuery: String!) {
      repository(owner: $owner, name: $name) {
        defaultBranchRef {
          target {
            ... on Commit {
              history(since: $since) {
                totalCount
                nodes {
                  author {
                    email
                    user {
                      id
                    }
                  }
                }
              }
            }
          }
        }
        forks(first: 100, orderBy: {field: CREATED_AT, direction: DESC}) {
          nodes {
            createdAt
          }
        }
      }
      closedIssues: search(query: $issueClosedQuery, type: ISSUE, first: 1) {
        issueCount
      }
      openedIssues: search(query: $issueOpenedQuery, type: ISSUE, first: 1) {
        issueCount
      }
      rateLimit {
        remaining
      }
    }
    """
    variables = {
        "owner": owner,
        "name": name,
        "since": since_iso,
        "issueClosedQuery": issue_closed_query,
        "issueOpenedQuery": issue_opened_query
    }

    try:
        response = await client.post(GRAPHQL_URL, json={"query": query, "variables": variables})
        response.raise_for_status()
        data = response.json()
        
        rate_limit = data.get("data", {}).get("rateLimit", {}).get("remaining", 5000)
        if rate_limit < 500:
            print(f"WARNING: GitHub GraphQL budget low ({rate_limit} remaining).")

        # `reserve` is the budget this caller must leave untouched. The scheduled
        # scraper passes a large reserve so customer-facing on-demand fetches retain
        # headroom; on-demand callers pass 0 and may consume the whole remainder.
        if rate_limit <= reserve:
            print(f"BUDGET: GraphQL remaining={rate_limit}, reserve={reserve}. Halting this caller.")
            return {"rate_limited": True}

        repo_data = data.get("data", {}).get("repository", {})
        if not repo_data or not repo_data.get("defaultBranchRef"):
             return None

        history = repo_data["defaultBranchRef"]["target"]["history"]
        total_commits_past_24h = history["totalCount"]
        
        unique_authors = set()
        for node in history["nodes"]:
            author = node.get("author", {})
            identifier = author.get("email") or str(author.get("user", {}).get("id"))
            if identifier:
                unique_authors.add(identifier)
        
        unique_commit_authors_past_24h = len(unique_authors)

        if total_commits_past_24h == 0:
            contributor_churn = 0.0
        else:
            contributor_churn = 1.0 - (unique_commit_authors_past_24h / total_commits_past_24h)

        forks_data = repo_data.get("forks", {}).get("nodes", [])
        now_dt = datetime.now(timezone.utc)
        thirty_days_ago = now_dt - timedelta(days=30)
        
        fork_velocity_24h = sum(1 for f in forks_data if datetime.fromisoformat(f["createdAt"].replace('Z', '+00:00')) >= since_dt)
        
        # Calculate fork spike ratio based on up to 100 recent forks
        forks_30d = sum(1 for f in forks_data if datetime.fromisoformat(f["createdAt"].replace('Z', '+00:00')) >= thirty_days_ago)
        daily_avg = forks_30d / 30.0
        
        fork_spike_ratio = None
        if daily_avg > 0:
            fork_spike_ratio = fork_velocity_24h / daily_avg
        elif fork_velocity_24h > 0:
            fork_spike_ratio = float(fork_velocity_24h) # Infinite ratio effectively

        closed_issues = data.get("data", {}).get("closedIssues", {}).get("issueCount", 0)
        opened_issues = data.get("data", {}).get("openedIssues", {}).get("issueCount", 0)
        open_issues_delta = opened_issues - closed_issues

        return {
            "rate_limited": False,
            "commit_velocity_24h": total_commits_past_24h,
            "open_issues_delta": open_issues_delta,
            "fork_velocity_24h": fork_velocity_24h,
            "contributor_churn": float(contributor_churn),
            "fork_spike_ratio": fork_spike_ratio
        }
    except Exception as e:
        print(f"Failed to fetch {github_repo}: {e}")
        return None

async def fetch_npm_metrics(client: httpx.AsyncClient, package_name: str) -> dict:
    try:
        response = await client.get(f"https://registry.npmjs.org/{package_name}")
        if response.status_code != 200:
            return {}
        data = response.json()
        
        maintainers = data.get("maintainers", [])
        # Absent maintainer metadata is NOT evidence of a single maintainer.
        # Substituting 1 here produced a fabricated MCI of 10.0 (maximum risk) out of
        # missing data. None makes calculate_mci return "insufficient data" instead.
        maintainer_count = len(maintainers) if maintainers else None
        
        time_data = data.get("time", {})
        release_times = []
        for version, t_str in time_data.items():
            if version not in ("modified", "created"):
                try:
                    dt = datetime.fromisoformat(t_str.replace('Z', '+00:00'))
                    release_times.append(dt)
                except ValueError:
                    pass
                    
        days_since_last_publish = None
        publish_cadence_variance = None
        
        if release_times:
            release_times.sort()
            latest = release_times[-1]
            days_since_last_publish = (datetime.now(timezone.utc) - latest).days
            
            twelve_months_ago = datetime.now(timezone.utc) - timedelta(days=365)
            recent_releases = [rt for rt in release_times if rt >= twelve_months_ago]
            publish_cadence_variance = calculate_variance(recent_releases)
            
        return {
            "maintainer_count": maintainer_count,
            "days_since_last_publish": days_since_last_publish,
            "publish_cadence_variance": publish_cadence_variance,
        }
    except Exception as e:
        print(f"Failed to fetch NPM metrics for {package_name}: {e}")
        return {}

async def fetch_pypi_metrics(client: httpx.AsyncClient, package_name: str) -> dict:
    try:
        response = await client.get(f"https://pypi.org/pypi/{package_name}/json")
        if response.status_code != 200:
            return {}
        data = response.json()
        
        releases = data.get("releases", {})
        release_times = []
        for version, release_list in releases.items():
            for r in release_list:
                t_str = r.get("upload_time_iso_8601")
                if t_str:
                    try:
                        dt = datetime.fromisoformat(t_str.replace('Z', '+00:00'))
                        release_times.append(dt)
                    except ValueError:
                        pass
        
        days_since_last_publish = None
        publish_cadence_variance = None
        
        if release_times:
            release_times.sort()
            latest = release_times[-1]
            days_since_last_publish = (datetime.now(timezone.utc) - latest).days
            
            twelve_months_ago = datetime.now(timezone.utc) - timedelta(days=365)
            recent_releases = [rt for rt in release_times if rt >= twelve_months_ago]
            publish_cadence_variance = calculate_variance(recent_releases)
            
        return {
            # EXPLICIT CAVEAT: PyPI does not expose valid maintainers.
            "maintainer_count": None,
            "days_since_last_publish": days_since_last_publish,
            "publish_cadence_variance": publish_cadence_variance,
        }
    except Exception as e:
        print(f"Failed to fetch PyPI metrics for {package_name}: {e}")
        return {}

from core.config import settings

async def ingest_metrics():
    github_token = settings.GITHUB_TOKEN
    if not github_token:
        print("CRITICAL: GITHUB_TOKEN environment variable missing.")
        return

    since_dt = datetime.now(timezone.utc) - timedelta(days=1)
    
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Content-Type": "application/json",
    }

    metrics_payload = []
    # Leave headroom for customer-facing on-demand fetches, which take priority
    # over background pre-warming.
    reserve = settings.GITHUB_RATELIMIT_RESERVE
    skipped_unqueryable = 0
    halted_on_budget = False

    async with httpx.AsyncClient(headers=headers, timeout=20.0) as client:
        targets = await discover_target_packages(client)

        for pkg in targets:
            pkg_name = pkg["name"]
            ecosystem = pkg["ecosystem"]
            github_repo = pkg["github"]
            
            gh_result = await fetch_github_metrics(client, github_repo, since_dt, reserve=reserve)
            if not gh_result:
                skipped_unqueryable += 1
                continue
            if gh_result.get("rate_limited"):
                halted_on_budget = True
                print(f"BUDGET HALT: reserve of {reserve} reached. Saving current payload...")
                break
            gh_result.pop("rate_limited")
            
            reg_result = {}
            if ecosystem == "npm":
                reg_result = await fetch_npm_metrics(client, pkg_name)
            elif ecosystem == "pypi":
                reg_result = await fetch_pypi_metrics(client, pkg_name)
                
            maintainer_count = reg_result.get("maintainer_count")
            
            payload = {
                "package_name": f"{ecosystem}/{pkg_name}",
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
            
            metrics_payload.append(payload)
            await asyncio.sleep(0.1)

    # No silent caps: report coverage including what was dropped and why, so a
    # truncated run is never mistaken for full catalog coverage.
    print(
        f"INGEST SUMMARY: discovered={len(targets)} ingested={len(metrics_payload)} "
        f"skipped_unqueryable={skipped_unqueryable} halted_on_budget={halted_on_budget}"
    )

    if not metrics_payload:
        print("No metrics extracted. Exiting.")
        return

    async with AsyncSessionLocal() as session:
        stmt = insert(PackageRiskMetric).values(metrics_payload)
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
    print(f"Successfully ingested {len(metrics_payload)} records into package_risk_metrics ledger.")

if __name__ == "__main__":
    asyncio.run(ingest_metrics())
