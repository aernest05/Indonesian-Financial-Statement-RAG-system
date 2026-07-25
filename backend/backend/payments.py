"""Midtrans Snap payment integration: transaction creation and notification handling."""

import base64
import hashlib
import os
import time
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
import requests
from backend.auth import _supabase

MIDTRANS_SERVER_KEY = os.environ.get("MIDTRANS_SERVER_KEY", "")
MIDTRANS_IS_PRODUCTION = os.environ.get("MIDTRANS_IS_PRODUCTION", "false").lower() == "true"
MIDTRANS_PRICE = int(os.environ.get("MIDTRANS_PRICE", "40000"))
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

SNAP_BASE_URL = (
    "https://app.midtrans.com/snap/v1"
    if MIDTRANS_IS_PRODUCTION
    else "https://app.sandbox.midtrans.com/snap/v1"
)

SUBSCRIPTION_DAYS = 30


def _auth_header() -> dict:
    token = base64.b64encode(f"{MIDTRANS_SERVER_KEY}:".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def create_checkout_session(user_id: str, user_email: str) -> str:
    """Create a Midtrans Snap transaction and return the redirect URL."""
    order_id = f"{user_id}-{int(time.time())}"

    body = {
        "transaction_details": {
            "order_id": order_id,
            "gross_amount": MIDTRANS_PRICE,
        },
        "customer_details": {"email": user_email},
        "item_details": [{
            "id": "pro-monthly",
            "price": MIDTRANS_PRICE,
            "quantity": 1,
            "name": "FinSage Pro - 1 bulan",
        }],
        "custom_field1": user_id,
        "callbacks": {"finish": f"{FRONTEND_URL}/app?payment=success"},
    }

    resp = requests.post(f"{SNAP_BASE_URL}/transactions", json=body, headers=_auth_header())
    if not resp.ok:
        raise HTTPException(status_code=502, detail="Failed to create payment session")

    return resp.json()["redirect_url"]


async def handle_notification(request: Request) -> dict:
    """Verify and process a Midtrans payment notification."""
    body = await request.json()

    order_id = body.get("order_id", "")
    status_code = body.get("status_code", "")
    gross_amount = body.get("gross_amount", "")
    signature_key = body.get("signature_key", "")

    expected = hashlib.sha512(
        f"{order_id}{status_code}{gross_amount}{MIDTRANS_SERVER_KEY}".encode()
    ).hexdigest()
    if signature_key != expected:
        raise HTTPException(status_code=400, detail="Invalid signature")

    user_id = body.get("custom_field1")
    if not user_id:
        return {"status": "ignored"}

    transaction_status = body.get("transaction_status")
    fraud_status = body.get("fraud_status")

    if transaction_status in ("capture", "settlement") and fraud_status in (None, "accept"):
        sb = _supabase()
        expires_at = (datetime.now(timezone.utc) + timedelta(days=SUBSCRIPTION_DAYS)).isoformat()
        sb.table("subscriptions").upsert({
            "user_id": user_id,
            "status": "active",
            "expires_at": expires_at,
            "midtrans_order_id": order_id,
            "midtrans_transaction_id": body.get("transaction_id"),
        }, on_conflict="user_id").execute()

    return {"status": "ok"}
