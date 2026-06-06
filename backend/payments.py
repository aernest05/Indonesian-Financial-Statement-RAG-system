"""Stripe payment integration: checkout session creation and webhook handling."""

import os
import stripe
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
from backend.auth import _supabase

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")


def create_checkout_session(user_id: str, user_email: str) -> str:
    """Create a Stripe Checkout session and return the URL."""
    sb = _supabase()

    # Reuse existing Stripe customer if we have one
    sub = (
        sb.table("subscriptions")
        .select("stripe_customer_id")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    customer_id = sub.data.get("stripe_customer_id") if sub.data else None

    params: dict = {
        "mode": "subscription",
        "line_items": [{"price": STRIPE_PRICE_ID, "quantity": 1}],
        "success_url": f"{FRONTEND_URL}?payment=success",
        "cancel_url": f"{FRONTEND_URL}?payment=cancelled",
        "metadata": {"user_id": user_id},
        "subscription_data": {"metadata": {"user_id": user_id}},
    }

    if customer_id:
        params["customer"] = customer_id
    else:
        params["customer_email"] = user_email

    session = stripe.checkout.Session.create(**params)
    return session.url


async def handle_webhook(request: Request) -> dict:
    """Verify and process Stripe webhook events."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except stripe.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    sb = _supabase()

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("metadata", {}).get("user_id")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        if not user_id:
            return {"status": "ignored"}

        # Fetch subscription end date from Stripe
        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        expires_at = datetime.fromtimestamp(
            stripe_sub["current_period_end"], tz=timezone.utc
        ).isoformat()

        sb.table("subscriptions").upsert({
            "user_id": user_id,
            "status": "active",
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "expires_at": expires_at,
        }, on_conflict="user_id").execute()

    elif event["type"] == "customer.subscription.deleted":
        subscription_id = event["data"]["object"]["id"]
        sb.table("subscriptions").update({
            "status": "expired",
            "expires_at": datetime.now(timezone.utc).isoformat(),
        }).eq("stripe_subscription_id", subscription_id).execute()

    elif event["type"] == "invoice.payment_succeeded":
        invoice = event["data"]["object"]
        subscription_id = invoice.get("subscription")
        # Only process renewal invoices (billing_reason = subscription_cycle), not the first payment
        # (that's already handled by checkout.session.completed)
        if subscription_id and invoice.get("billing_reason") == "subscription_cycle":
            stripe_sub = stripe.Subscription.retrieve(subscription_id)
            expires_at = datetime.fromtimestamp(
                stripe_sub["current_period_end"], tz=timezone.utc
            ).isoformat()
            sb.table("subscriptions").update({
                "status": "active",
                "expires_at": expires_at,
            }).eq("stripe_subscription_id", subscription_id).execute()

    elif event["type"] == "invoice.payment_failed":
        subscription_id = event["data"]["object"].get("subscription")
        if subscription_id:
            sb.table("subscriptions").update({"status": "expired"}).eq(
                "stripe_subscription_id", subscription_id
            ).execute()

    return {"status": "ok"}
