"""Auth middleware: JWT verification + quota enforcement via Supabase."""

import os
from datetime import date, datetime, timezone
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


def _is_active(sub_data: dict | None) -> bool:
    """True if the subscription row is marked active AND not past its expiry.

    Unlike Stripe, Midtrans has no recurring engine that pushes a "subscription
    ended" event when a paid period lapses, so expiry must be checked here
    rather than relying solely on the `status` column staying in sync.
    """
    if not sub_data or sub_data.get("status") != "active":
        return False
    expires_at = sub_data.get("expires_at")
    if not expires_at:
        return False
    return datetime.fromisoformat(expires_at) > datetime.now(timezone.utc)


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


def require_auth_with_email(request: Request) -> tuple[str, str]:
    """Raise 401 if no valid JWT. Returns (user_id, email).

    Uses the same token verification as require_auth rather than the
    admin API, since the admin API authenticates as the service key
    itself (separate failure mode from verifying the user's own token).
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = auth.removeprefix("Bearer ").strip()
    try:
        response = _supabase().auth.get_user(token)
    except Exception:
        response = None
    if not response or not response.user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return response.user.id, response.user.email or ""


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

    if _is_active(sub.data if sub else None):
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

    if usage and usage.data:
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

    sub_data = sub.data if sub else None
    usage_data = usage.data if usage else None

    raw_status = sub_data.get("status", "free") if sub_data else "free"
    status = "active" if _is_active(sub_data) else ("expired" if raw_status == "active" else raw_status)
    queries_today = usage_data["count"] if usage_data else 0

    return {
        "status": status,
        "queries_today": queries_today,
        "daily_limit": None if status == "active" else FREE_QUERIES_PER_DAY,
        "expires_at": sub_data.get("expires_at") if sub_data else None,
    }
