"""Auth middleware: JWT verification + quota enforcement via Supabase."""

import os
from datetime import date
from fastapi import HTTPException, Request
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
FREE_QUERIES_PER_DAY = int(os.environ.get("FREE_QUERIES_PER_DAY", "5"))

_client: Client | None = None


def _supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def get_user_id(request: Request) -> str | None:
    """Extract and verify the Supabase JWT from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.removeprefix("Bearer ").strip()
    try:
        response = _supabase().auth.get_user(token)
        return response.user.id if response.user else None
    except Exception:
        return None


def require_auth(request: Request) -> str:
    """Raise 401 if no valid JWT. Returns user_id."""
    user_id = get_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


def check_and_increment_quota(user_id: str) -> None:
    """
    Check daily quota for free users. Raises 429 if exceeded.
    Paid users (active subscription) are always allowed through.
    """
    sb = _supabase()
    today = date.today().isoformat()

    # Check subscription status
    sub = (
        sb.table("subscriptions")
        .select("status, expires_at")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    if sub.data and sub.data.get("status") == "active":
        return  # paid user — no quota

    # Free user: upsert today's usage row and check count
    usage = (
        sb.table("query_usage")
        .select("id, count")
        .eq("user_id", user_id)
        .eq("date", today)
        .maybe_single()
        .execute()
    )

    if usage.data:
        current = usage.data["count"]
        if current >= FREE_QUERIES_PER_DAY:
            raise HTTPException(
                status_code=429,
                detail=f"Daily limit of {FREE_QUERIES_PER_DAY} queries reached. Upgrade to continue."
            )
        sb.table("query_usage").update({"count": current + 1}).eq("id", usage.data["id"]).execute()
    else:
        sb.table("query_usage").insert({"user_id": user_id, "date": today, "count": 1}).execute()


def get_subscription_status(user_id: str) -> dict:
    """Return subscription info for a user."""
    sb = _supabase()
    today = date.today().isoformat()

    sub = (
        sb.table("subscriptions")
        .select("status, expires_at")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    usage = (
        sb.table("query_usage")
        .select("count")
        .eq("user_id", user_id)
        .eq("date", today)
        .maybe_single()
        .execute()
    )

    status = sub.data.get("status", "free") if sub.data else "free"
    queries_today = usage.data["count"] if usage.data else 0

    return {
        "status": status,
        "queries_today": queries_today,
        "daily_limit": None if status == "active" else FREE_QUERIES_PER_DAY,
        "expires_at": sub.data.get("expires_at") if sub.data else None,
    }
