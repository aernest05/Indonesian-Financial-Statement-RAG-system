"""LangSearch reranking + time bonus scoring."""

import json
import os
import requests
from datetime import datetime
from langchain_core.documents import Document

_CURRENT_YEAR = datetime.now().year


def _langsearch_rerank(query: str, documents: list[str], k: int = 10) -> list[float]:
    """Call the LangSearch reranker API and return relevance scores."""
    url = "https://api.langsearch.com/v1/rerank"
    payload = json.dumps({
        "model": "langsearch-reranker-v1",
        "query": query,
        "top_n": k,
        "return_documents": True,
        "documents": documents,
    })
    headers = {
        "Authorization": f"Bearer {os.environ.get('LANGSEARCH_API_KEY', '')}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()
    data = response.json()
    return [r["relevance_score"] for r in data["results"]]


def _time_bonus(doc_year: int | None, query_year: int | None) -> float:
    """Small additive bonus [0, 0.1] for documents close to the reference year."""
    ref = query_year or _CURRENT_YEAR
    if doc_year is None:
        return 0.0
    diff = abs(ref - doc_year)
    if diff == 0:
        return 0.10
    if diff == 1:
        return 0.05
    return 0.0


def rerank(
    query: str,
    docs: list[Document],
    k: int = 5,
    year_hint: int | None = None,
) -> list[Document]:
    """LangSearch reranking + time bonus. Falls back to truncation if API call fails."""
    if not docs:
        return docs

    try:
        ce_scores = _langsearch_rerank(query, [d.page_content for d in docs], k)
    except Exception as e:
        print(f"[Reranker] LangSearch call failed ({e}) — falling back to truncation")
        return docs[:k]

    bonuses = [_time_bonus(d.metadata.get("year"), year_hint) for d in docs]
    final = [float(s) + b for s, b in zip(ce_scores, bonuses)]

    ranked = sorted(zip(final, docs), key=lambda x: x[0], reverse=True)
    return [d for _, d in ranked[:k]]
