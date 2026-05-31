import os
import httpx


def log_query(
    question: str,
    response_preview: str = "",
    ticker: str = "",
    user_ref: str = "",
    hit_rate_limit: bool = False,
) -> None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        return
    endpoint = f"{url}/rest/v1/query_logs"
    try:
        httpx.post(
            endpoint,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json={
                "user_ref": user_ref,
                "question": question,
                "response_preview": response_preview[:200],
                "ticker": ticker,
                "hit_rate_limit": hit_rate_limit,
            },
            timeout=5,
        )
    except Exception as e:
        print(f"[logger] failed to log query: {e}")
