"""retrieval.py — Multi-path Retrieval (MPR) pipeline.

Implements FinSage §3.2 and §3.3 without re-embedding stored documents:
  - BM25 sparse retrieval           (rank-bm25, index built lazily from Chroma)
  - Dense retrieval                  (existing Chroma embeddings)
  - HyDE retrieval                   (hypothetical answer embedded at query time)
  - Metadata TF-IDF retrieval        (query vs section_summary fields)
  - Chunk bundling / page expansion  (add neighboring-page chunks)
  - Cross-encoder re-ranking         (sentence-transformers, optional)
  - Time bonus                       (year metadata → recency boost)
"""

import json as _json
import requests
from datetime import datetime
import streamlit as st
from backend.ingestion import setup_retriever
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from backend.retrieval_methods import _hyde_retrieve, _bm25_retrieve, _metadata_retrieve, _dense_retrieve

from backend.query_processing import (
    get_year_filter,
    process_query
)

# ── LLM ──────────────────────────────────────────────────────────────────────
_llm = None

def _get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            api_key=st.secrets['DEEPSEEK_API_KEY'],
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            temperature=0.7,
        )
    return _llm
# ── LangSearch reranker ───────────────────────────────────────────────────────

def _langsearch_rerank(query: str, documents: list[str], k: int = 10) -> list[float]:
    """Call the LangSearch reranker API and return relevance scores."""
    url = "https://api.langsearch.com/v1/rerank"
    payload = _json.dumps({
        "model": "langsearch-reranker-v1",
        "query": query,
        "top_n": k,
        "return_documents": True,
        "documents": documents,
    })
    headers = {
        "Authorization": f"Bearer {st.secrets['LANGSEARCH_API_KEY']}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()
    data = response.json()
    return [r["relevance_score"] for r in data["results"]]


# ── Chunk bundling (page-neighbor expansion) ─────────────────────────────────

def _expand_chunks(docs: list[Document], db) -> list[Document]:
    """
    For each retrieved chunk, add chunks from the same source file on
    adjacent pages (page ± 1).  Uses the in-memory BM25 cache to avoid
    extra Chroma queries.  (FinSage §3.2 Chunk Bundling)
    """
    _, all_docs = _load_bm25(db)

    seen = {d.page_content for d in docs}
    expanded = list(docs)

    for doc in docs:
        page = doc.metadata.get("page")
        source = doc.metadata.get("source")
        if page is None or source is None:
            continue
        for raw in all_docs:
            raw_page = raw["metadata"].get("page")
            raw_source = raw["metadata"].get("source")
            if (
                raw_source == source
                and raw_page in (page - 1, page + 1)
                and raw["page_content"] not in seen
            ):
                seen.add(raw["page_content"])
                expanded.append(
                    Document(
                        page_content=raw["page_content"],
                        metadata=raw["metadata"],
                    )
                )
    return expanded


# ── Re-ranking with time bonus ────────────────────────────────────────────────

_CURRENT_YEAR = datetime.now().year


def _time_bonus(doc_year: int | None, query_year: int | None) -> float:
    """
    Small additive bonus [0, 0.1] for documents close to the reference year.
    (FinSage §3.3 Time bonus)
    """
    ref = query_year or _CURRENT_YEAR
    if doc_year is None:
        return 0.0
    diff = abs(ref - doc_year)
    if diff == 0:
        return 0.10
    if diff == 1:
        return 0.05
    return 0.0


def _rerank(
    query: str,
    docs: list[Document],
    k: int = 5,
    year_hint: int | None = None,
) -> list[Document]:
    """LangSearch reranking + time bonus.  Falls back to truncation if the
    API call fails.  (FinSage §3.3)"""
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


# ── Full MPR pipeline ─────────────────────────────────────────────────────────

def mpr_retrieve(
    sub_queries: list[str],
    db,
    year_filter: dict | None = None,
    k_per_retrieval_method: int = 10,
    k_per_queries: int = 5,
    year_hint: int | None = None,
    enable_bm25_retrieve: bool = True,
    enable_hyde: bool = True,
    enable_metadata: bool = True,
    enable_expansion: bool = True,
) -> list[Document]:
    """
    Multi-path Retrieval (FinSage §3.2):
      For each sub-query run BM25 + Dense + HyDE + Metadata retrievers,
      merge and deduplicate, expand chunks, then re-rank.
    """

    final = []

    for i,sq in enumerate(sub_queries):

        seen: dict[str, Document] = {}

        def _add(retrieved: list[Document]) -> None:
            for d in retrieved:
                if d.page_content not in seen:
                    seen[d.page_content] = d # content → doc (deduplication key)

        print(f"[MPR] sub-query: {sq!r}") 
        _add(_dense_retrieve(sq, db, k=k_per_retrieval_method, year_filter=year_filter))

        if enable_bm25_retrieve:
            _add(_bm25_retrieve(sq, db, k=k_per_retrieval_method))

        if enable_hyde:
            try:
                _add(_hyde_retrieve(sq, db, k=k_per_retrieval_method))
            except Exception as e:
                print(f"  [HyDE] skipped: {e}")

        if enable_metadata:
            _add(_metadata_retrieve(sq, db, k=k_per_retrieval_method))

        candidates = list(seen.values())
        print(f"[MPR] candidates for SQ{i+1} after multi-path: {len(candidates)}")

        if enable_expansion:
            candidates = _expand_chunks(candidates, db)
            print(f"[MPR] after chunk expansion: {len(candidates)}")

        candidates = _rerank(sq, candidates, k=k_per_queries, year_hint=year_hint)
        print(f"[MPR] candidates for SQ{i+1} after reranking: {len(candidates)}")
        final += candidates

    # Re-rank anchored on the first (primary) sub-query
    print(f"[MPR] final docs: {len(final)}")
    return final


# ── Answer generation ─────────────────────────────────────────────────────────

_ANSWER_PROMPT = ChatPromptTemplate.from_template("""Answer the user's question based on the following context:
{context}

Question: {input}

Respond in Indonesian.
""")


def prepare_retrieval(question: str) -> dict:
    """Run DB setup, query processing, and retrieval. Returns everything needed to generate an answer."""
    import time

    t0 = time.perf_counter()
    db = setup_retriever()
    t_db = time.perf_counter()

    processed = process_query(question)
    years: list[int] = processed.extracted_years
    operator: str = processed.operator
    sub_queries: list[str] = processed.sub_queries
    year_hint = years[0] if years else None
    year_filter = get_year_filter(years, operator) if years else None
    t_query = time.perf_counter()

    print(f"[MPR] sub-queries: {sub_queries}")

    docs = mpr_retrieve(
        sub_queries,
        db,
        year_filter=year_filter,
        year_hint=year_hint,
        enable_bm25_retrieve=False,
        enable_metadata=False,
        enable_hyde=True,
        enable_expansion=False
    )
    t_retrieval = time.perf_counter()

    return {
        "docs": docs,
        "context": "\n\n".join(d.page_content for d in docs),
        "extracted_years": years,
        "debug_info": {
            "original_query": question,
            "sub_queries": sub_queries,
            "extracted_years": years,
            "operator": operator,
        },
        "timings": {
            "db_setup_s": round(t_db - t0, 2),
            "query_processing_s": round(t_query - t_db, 2),
            "retrieval_s": round(t_retrieval - t_query, 2),
        },
        "_t_retrieval": t_retrieval,
        "_t0": t0,
    }


def stream_answer(question: str, retrieval: dict):
    """Yield LLM answer chunks. Call after prepare_retrieval."""
    import time

    prompt = _ANSWER_PROMPT.format(context=retrieval["context"], input=question)
    for chunk in _get_llm().stream(prompt):
        yield chunk.content

    t_llm = time.perf_counter()
    retrieval["timings"]["llm_s"] = round(t_llm - retrieval["_t_retrieval"], 2)
    retrieval["timings"]["total_s"] = round(t_llm - retrieval["_t0"], 2)


def answer_question(question: str) -> dict:
    retrieval = prepare_retrieval(question)
    full_answer = "".join(stream_answer(question, retrieval))
    return {
        "answer": full_answer,
        "context": retrieval["docs"],
        "extracted_years": retrieval["extracted_years"],
        "debug_info": retrieval["debug_info"],
        "timings": retrieval["timings"],
    }


if __name__ == "__main__":
    result = answer_question("BBCA performance in 2024")
    print(result["answer"])
