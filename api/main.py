import asyncio
import difflib
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Depends, HTTPException, status, Request, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, update, distinct
import uvicorn
import os
import hmac
import hashlib
import httpx

from db.connection import AsyncSessionLocal
from db.models import APIKey, PackageRiskMetric
from api.schemas import PackageRiskMetricResponse, AdvancedPackageRiskAnalyticsResponse
from api.deps import verify_api_key
from api.rate_limiter import enforce_rate_limit
from api.analytics import calculate_mci, calculate_dri, calculate_asi
from api.service import (
    resolve_and_fetch_package_metrics,
    RegistryNotFound,
    UntrackablePackage,
    UpstreamAuthUnavailable,
    UpstreamRateLimited,
)
from core.config import settings

# Enforce strict fail-fast perimeter checks on application boot
if not settings.RESEND_API_KEY:
    raise RuntimeError("CRITICAL: RESEND_API_KEY environment variable missing")
if not settings.DATABASE_URL:
    raise RuntimeError("CRITICAL: DATABASE_URL environment variable missing")
if not settings.REDIS_URL:
    raise RuntimeError("CRITICAL: REDIS_URL environment variable missing")
if not settings.RESEND_FROM_EMAIL:
    raise RuntimeError("CRITICAL: RESEND_FROM_EMAIL environment variable missing")
if not settings.API_KEY_SIGNING_SECRET:
    raise RuntimeError("CRITICAL: API_KEY_SIGNING_SECRET environment variable missing")

# GITHUB_TOKEN is deliberately NOT fail-fast. The scheduled Actions workflow is
# the visibility signal for the scraper path, and a hard boot failure here would
# take the whole API down for a capability that only affects on-demand fetches.
# Instead the request path surfaces its absence honestly as HTTP 503 — see
# UpstreamAuthUnavailable in api/service.py.
if not settings.GITHUB_TOKEN:
    print("WARNING: GITHUB_TOKEN unset. On-demand live fetch is disabled; "
          "cache misses will return HTTP 503 until it is configured.")

app = FastAPI(
    title="Data-as-a-Service Core",
    description="Maintainer & Dormancy Risk Signal DaaS",
    version="3.0"
)

class TyposquatException(Exception):
    def __init__(self, detail: str, possible_typosquat_of: str, similarity: float):
        self.detail = detail
        self.possible_typosquat_of = possible_typosquat_of
        self.similarity = similarity

@app.exception_handler(TyposquatException)
async def typosquat_exception_handler(request: Request, exc: TyposquatException):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": exc.detail,
            "status": "not_found",
            "possible_typosquat_of": exc.possible_typosquat_of,
            "similarity": round(exc.similarity, 3)
        }
    )

async def check_typosquat(package_name: str):
    """
    Ecosystem-scoped typosquatting detector.
    Strips ecosystem prefix, compares raw names against ecosystem candidates,
    logs matches >= 0.70 for threshold review, and raises TyposquatException if similarity >= 0.80.
    """
    parts = package_name.split("/", 1)
    if len(parts) != 2:
        return

    ecosystem, raw_name = parts[0].lower(), parts[1]

    async with AsyncSessionLocal() as session:
        stmt = select(distinct(PackageRiskMetric.package_name)).where(
            PackageRiskMetric.package_name.like(f"{ecosystem}/%")
        )
        res = await session.execute(stmt)
        known_packages = res.scalars().all()

    best_match = None
    best_similarity = 0.0

    for full_candidate in known_packages:
        cand_parts = full_candidate.split("/", 1)
        if len(cand_parts) == 2:
            cand_raw = cand_parts[1]
            similarity = difflib.SequenceMatcher(None, raw_name, cand_raw).ratio()

            if similarity >= 0.70:
                print(f"TYPOSQUAT MATCH LOG: '{package_name}' vs candidate '{full_candidate}' -> similarity={similarity:.3f}")

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = full_candidate

    if best_similarity >= 0.80 and best_match:
        raise TyposquatException(
            detail=f"Package identity '{package_name}' does not exist in registry.",
            possible_typosquat_of=best_match,
            similarity=best_similarity
        )

async def get_or_fetch_package_metric(package_name: str, background_tasks: BackgroundTasks) -> PackageRiskMetric:
    """
    Cache-aware resolver. Handles cache hits, background revalidation (stale > CACHE_TTL_HOURS),
    and synchronous on-demand fetches with 5.0s timeout backpressure.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(PackageRiskMetric).where(
            PackageRiskMetric.package_name == package_name
        ).order_by(PackageRiskMetric.timestamp.desc()).limit(1)

        res = await session.execute(stmt)
        metric_node = res.scalars().first()

    now = datetime.now(timezone.utc)
    ttl_delta = timedelta(hours=settings.CACHE_TTL_HOURS)

    if metric_node and metric_node.timestamp:
        ts = metric_node.timestamp.replace(tzinfo=timezone.utc) if metric_node.timestamp.tzinfo is None else metric_node.timestamp
        if (now - ts) < ttl_delta:
            return metric_node
        else:
            # Return cached node immediately, refresh in background
            background_tasks.add_task(resolve_and_fetch_package_metrics, package_name)
            return metric_node

    # Not found -> On-Demand synchronous fetch with 5.0s timeout backpressure
    try:
        new_metric = await asyncio.wait_for(
            resolve_and_fetch_package_metrics(package_name),
            timeout=5.0
        )
        return new_metric
    except asyncio.TimeoutError:
        background_tasks.add_task(resolve_and_fetch_package_metrics, package_name)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Resolution timeout: package telemetry is being fetched in the background. Retry shortly."
        )
    except RegistryNotFound:
        await check_typosquat(package_name)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Package identity '{package_name}' does not exist in registry."
        )
    except UntrackablePackage as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    # Upstream problems are OUR failure, not evidence about the package. Returning
    # 404 here would tell a customer their real, trackable package is untrackable.
    except UpstreamAuthUnavailable as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except UpstreamRateLimited as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal resolver error: {e}"
        )

@app.post("/webhooks/lemon-squeezy")
@app.post("/api/v1/webhooks/lemon-squeezy")
async def lemon_squeezy_webhook(request: Request):
    """
    Cryptographic Webhook Receiver for Lemon Squeezy MoR.
    Strictly verifies HMAC signatures to allocate API tokens securely.
    """
    if not settings.LEMON_SQUEEZY_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CRITICAL: LEMON_SQUEEZY_WEBHOOK_SECRET environment variable missing"
        )

    x_signature = request.headers.get("X-Signature")
    if not x_signature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature headers")

    raw_body = await request.body()

    digest = hmac.new(
        settings.LEMON_SQUEEZY_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(digest, x_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature authentication forgery detected")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unparsable JSON transmission")

    meta = payload.get("meta", {})
    event_name = meta.get("event_name")

    valid_events = ["subscription_created", "subscription_payment_success", "subscription_updated", "subscription_cancelled", "subscription_expired"]
    if event_name not in valid_events:
        return {"status": "Event ignored properly"}

    data = payload.get("data", {})
    attributes = data.get("attributes", {})
    user_email = attributes.get("user_email")
    variant_id = attributes.get("variant_id")
    subscription_id = data.get("id")

    if not user_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing user_email payload structure")

    key_dispatched = False

    if event_name == "subscription_created":
        if settings.LEMON_SQUEEZY_VARIANT_ID and str(variant_id) != str(settings.LEMON_SQUEEZY_VARIANT_ID):
            return {"status": "Ignored - different product variant"}

        # Derive the raw key deterministically from the subscription id so a retried
        # webhook regenerates the IDENTICAL key. Only the SHA-256 digest is ever
        # persisted, so a randomly generated key could never be re-sent on retry.
        # (Per-customer rotation would need a salt column; not required today.)
        raw_api_key = "daas_live_" + hmac.new(
            settings.API_KEY_SIGNING_SECRET.encode("utf-8"),
            f"apikey:v1:{subscription_id}".encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        hashed_api_key = hashlib.sha256(raw_api_key.encode("utf-8")).hexdigest()

        # Idempotent provisioning: subscription_id carries a UNIQUE constraint, so a
        # blind insert would make every retry fail on the constraint instead.
        async with AsyncSessionLocal() as session:
            existing_res = await session.execute(
                select(APIKey).where(APIKey.subscription_id == str(subscription_id))
            )
            existing_key = existing_res.scalars().first()

            if existing_key:
                existing_key.valid_api_keys = hashed_api_key
                existing_key.is_active = True
            else:
                session.add(APIKey(
                    valid_api_keys=hashed_api_key,
                    subscription_id=str(subscription_id),
                    is_active=True
                ))
            await session.commit()

        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "from": settings.RESEND_FROM_EMAIL,
                        "to": [user_email],
                        "subject": "Your Maintainer Risk DaaS API Key",
                        "html": f"<p>Thank you for subscribing. Your API key is: <strong>{raw_api_key}</strong></p>"
                    },
                    timeout=10.0
                )
                res.raise_for_status()
                key_dispatched = True
        except Exception as e:
            print(f"CRITICAL ALERT: Failed to dispatch API key email to {user_email}. Error: {e}")
            key_dispatched = False

        # The key row is already committed, so a retry is safe and converges on the
        # same credential. Returning 2xx here would tell Lemon Squeezy the customer
        # was served when they in fact received nothing.
        if not key_dispatched:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API key persisted but delivery failed; webhook retry expected."
            )

    elif event_name in ["subscription_payment_success", "subscription_updated"]:
        # Renewal or resubscribe-after-cancel. Reactivate the existing credential;
        # do not re-issue or re-send on every successful renewal payment.
        async with AsyncSessionLocal() as session:
            stmt = update(APIKey).where(APIKey.subscription_id == str(subscription_id)).values(is_active=True)
            await session.execute(stmt)
            await session.commit()

    elif event_name in ["subscription_cancelled", "subscription_expired"]:
        async with AsyncSessionLocal() as session:
            stmt = update(APIKey).where(APIKey.subscription_id == str(subscription_id)).values(is_active=False)
            await session.execute(stmt)
            await session.commit()
            print(f"Subscription {subscription_id} cancelled/expired. Key deactivated.")

    return {
        "status": "success",
        "provisioned": event_name == "subscription_created",
        "key_dispatched": key_dispatched
    }

@app.get("/", description="Check the application's health")
async def GetHealth():
    return {"status": "online"}

# -----------------------------------------------------------------------------
# CRITICAL ROUTE REGISTRATION ORDER:
# /history MUST be registered BEFORE the greedy {package_name:path} routes!
# -----------------------------------------------------------------------------

@app.get("/api/v1/package-risk/{package_name:path}/history")
async def get_package_risk_history(
    package_name: str,
    limit: int = Query(default=30, ge=1, le=100),
    auth_key: APIKey = Depends(verify_api_key)
):
    """
    Returns time-series history of risk metrics and computed indices for package_name.
    Registered BEFORE general package-risk route to prevent greedy path hijacking.
    """
    await enforce_rate_limit(api_key_hash=auth_key.valid_api_keys, limit=60, window_secs=60)

    async with AsyncSessionLocal() as session:
        stmt = select(PackageRiskMetric).where(
            PackageRiskMetric.package_name == package_name
        ).order_by(PackageRiskMetric.timestamp.desc()).limit(limit)

        res = await session.execute(stmt)
        records = res.scalars().all()

        if not records:
            await check_typosquat(package_name)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Package identity '{package_name}' yields zero physical records."
            )

        history_list = []
        for metric_node in records:
            history_list.append({
                "package_name": metric_node.package_name,
                "timestamp": metric_node.timestamp,
                "maintainer_concentration_index": calculate_mci(metric_node),
                "dormancy_reactivation_index": calculate_dri(metric_node),
                "anomalous_spike_index": calculate_asi(metric_node),
                "maintainer_count": metric_node.maintainer_count,
                "single_maintainer_flag": metric_node.single_maintainer_flag,
                "days_since_last_publish": metric_node.days_since_last_publish,
                "publish_cadence_variance": metric_node.publish_cadence_variance,
                "fork_spike_ratio": metric_node.fork_spike_ratio,
            })
        return history_list

@app.get("/api/v1/analytics/package-risk/{package_name:path}", response_model=AdvancedPackageRiskAnalyticsResponse)
async def get_package_risk_analytics(
    package_name: str,
    background_tasks: BackgroundTasks,
    auth_key: APIKey = Depends(verify_api_key)
):
    """
    Synthesizes raw metrics into institutional composite indices (MCI, DRI, ASI).
    Executes lazy on-demand fetch with 5s backpressure on cache misses.
    """
    await enforce_rate_limit(api_key_hash=auth_key.valid_api_keys, limit=60, window_secs=60)
    metric_node = await get_or_fetch_package_metric(package_name, background_tasks)
    return {
        "package_name": metric_node.package_name,
        "timestamp": metric_node.timestamp,
        "maintainer_concentration_index": calculate_mci(metric_node),
        "dormancy_reactivation_index": calculate_dri(metric_node),
        "anomalous_spike_index": calculate_asi(metric_node),
        "maintainer_count": metric_node.maintainer_count,
        "single_maintainer_flag": metric_node.single_maintainer_flag,
        "days_since_last_publish": metric_node.days_since_last_publish,
        "publish_cadence_variance": metric_node.publish_cadence_variance,
        "fork_spike_ratio": metric_node.fork_spike_ratio,
    }

@app.get("/api/v1/package-risk/{package_name:path}", response_model=PackageRiskMetricResponse)
async def get_package_risk(
    package_name: str,
    background_tasks: BackgroundTasks,
    auth_key: APIKey = Depends(verify_api_key)
):
    """
    Returns latest raw package_risk_metrics row.
    Executes lazy on-demand fetch with 5s backpressure on cache misses.
    """
    await enforce_rate_limit(api_key_hash=auth_key.valid_api_keys, limit=60, window_secs=60)
    metric_node = await get_or_fetch_package_metric(package_name, background_tasks)
    return metric_node

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, env_file=".env", reload=True)
