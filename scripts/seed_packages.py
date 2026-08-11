"""
Seed packages into the cache directly, bypassing the API's 5-second backpressure budget.

Why this exists
---------------
The on-demand path in api/main.py gives a live fetch 5.0 seconds and returns HTTP 504 if it
overruns. On the Render free tier a large package can exceed that budget every time — the
npm packument for `react` alone is 6.5 MB and the GitHub GraphQL leg costs ~2.5-3.0s before
any parsing — so such a package can never populate its own cache entry through the API.

This calls the same resolver the API calls, with no time limit, and writes through the same
upsert. Once a row exists, the API serves it from cache: fresh rows are served directly and
stale rows are still served immediately while refreshing in the background, so a package only
has to be seeded once.

Typosquat detection also compares only against package names already stored, so seeding is a
prerequisite for that feature returning anything at all.

    PYTHONPATH=. python scripts/seed_packages.py npm/react npm/express pypi/requests

Run it against the SAME DATABASE_URL the deployed API uses, or you will seed the wrong
database. GITHUB_TOKEN must be set locally; this script does its own fetching and does not
go through Render.
"""
import argparse
import asyncio
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import settings
from api.service import (
    resolve_and_fetch_package_metrics,
    RegistryNotFound,
    UntrackablePackage,
    UpstreamAuthUnavailable,
    UpstreamRateLimited,
)

DEFAULT_PACKAGES = [
    "npm/react",
    "npm/express",
    "npm/axios",
    "pypi/requests",
    "pypi/flask",
]


async def seed(packages: list[str]) -> int:
    if not settings.DATABASE_URL:
        raise SystemExit("ABORT: DATABASE_URL is unset.")
    if not settings.GITHUB_TOKEN:
        raise SystemExit("ABORT: GITHUB_TOKEN is unset. Every fetch would fail.")

    failures = 0

    for name in packages:
        started = time.perf_counter()
        try:
            metric = await resolve_and_fetch_package_metrics(name)
            elapsed = time.perf_counter() - started

            if metric is None:
                print(f"  FAIL     {name:32s} resolver returned nothing after {elapsed:.2f}s")
                failures += 1
                continue

            over = "  (would have exceeded the API's 5s budget)" if elapsed > 5.0 else ""
            print(f"  SEEDED   {name:32s} {elapsed:5.2f}s  "
                  f"maintainers={metric.maintainer_count}{over}")

        except RegistryNotFound:
            print(f"  NOT_FOUND{name:32s} absent from the registry — check the spelling")
            failures += 1
        except UntrackablePackage as e:
            print(f"  SKIP     {name:32s} {e}")
            failures += 1
        except UpstreamAuthUnavailable as e:
            print(f"  FAIL     {name:32s} {e}")
            failures += 1
        except UpstreamRateLimited as e:
            print(f"  FAIL     {name:32s} {e}")
            failures += 1
        except ValueError as e:
            print(f"  FAIL     {name:32s} {e}")
            failures += 1

    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed package metrics directly, bypassing the API's 5s fetch budget."
    )
    parser.add_argument(
        "packages",
        nargs="*",
        default=DEFAULT_PACKAGES,
        help=f"Packages as ecosystem/name. Defaults to: {' '.join(DEFAULT_PACKAGES)}"
    )
    args = parser.parse_args()
    targets = args.packages or DEFAULT_PACKAGES

    print(f"\nSeeding {len(targets)} package(s)\n")
    failed = asyncio.run(seed(targets))
    print(f"\nDone. {len(targets) - failed} seeded, {failed} failed.\n")
    sys.exit(1 if failed else 0)
