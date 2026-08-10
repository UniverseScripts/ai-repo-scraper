"""
Mint a dedicated, revocable API key for an external reviewer (e.g. the Lemon Squeezy
store validation team) without routing them through a real paid checkout.

The derivation is identical to the `subscription_created` webhook handler in
api/main.py, so the issued key authenticates through the normal verify_api_key path
with no special-casing anywhere in the request pipeline.

Run it against the SAME DATABASE_URL and API_KEY_SIGNING_SECRET as the deployed API,
otherwise the derived key will not match what the live service expects.

    PYTHONPATH=. python scripts/provision_review_key.py --subscription-id sub_ls_review_2026
    PYTHONPATH=. python scripts/provision_review_key.py --subscription-id sub_ls_review_2026 --revoke

The raw key is printed once. Only its SHA-256 digest is persisted, so it cannot be
recovered from the database later — but because derivation is deterministic, re-running
this command with the same subscription id reproduces the identical key.
"""
import argparse
import asyncio
import hashlib
import hmac
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select

from core.config import settings
from db.connection import AsyncSessionLocal
from db.models import APIKey


def derive_raw_key(subscription_id: str) -> str:
    """Identical derivation to the subscription_created branch of the webhook."""
    return "daas_live_" + hmac.new(
        settings.API_KEY_SIGNING_SECRET.encode("utf-8"),
        f"apikey:v1:{subscription_id}".encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


async def provision(subscription_id: str, revoke: bool) -> None:
    if not settings.API_KEY_SIGNING_SECRET:
        raise SystemExit("ABORT: API_KEY_SIGNING_SECRET is unset. It must match the deployed API.")
    if not settings.DATABASE_URL:
        raise SystemExit("ABORT: DATABASE_URL is unset.")

    raw_key = derive_raw_key(subscription_id)
    hashed_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(APIKey).where(APIKey.subscription_id == subscription_id)
        )
        row = res.scalars().first()

        if revoke:
            if not row:
                print(f"No key exists for subscription_id={subscription_id!r}. Nothing to revoke.")
                return
            row.is_active = False
            await session.commit()
            print(f"REVOKED: subscription_id={subscription_id!r} -> is_active=False. Access terminated.")
            return

        if row:
            row.valid_api_keys = hashed_key
            row.is_active = True
        else:
            session.add(APIKey(
                valid_api_keys=hashed_key,
                subscription_id=subscription_id,
                is_active=True
            ))
        await session.commit()

    print("\nReviewer key provisioned.\n")
    print(f"  subscription_id : {subscription_id}")
    print(f"  X-API-Key       : {raw_key}\n")
    print("Revoke it when the review closes:")
    print(f"  PYTHONPATH=. python scripts/provision_review_key.py "
          f"--subscription-id {subscription_id} --revoke\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Provision or revoke a reviewer API key.")
    parser.add_argument(
        "--subscription-id",
        required=True,
        help="Synthetic subscription id for the reviewer, e.g. sub_ls_review_2026"
    )
    parser.add_argument(
        "--revoke",
        action="store_true",
        help="Deactivate the key instead of issuing one"
    )
    args = parser.parse_args()
    asyncio.run(provision(args.subscription_id, args.revoke))
