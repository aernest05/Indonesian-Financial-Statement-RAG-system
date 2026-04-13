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

import os
import json as _json
import requests
from datetime import datetime
from ingestion import embeddings, setup_retriever
import numpy as np
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosim


from query_processing import (
    generate_hyde_hypothesis,
    get_year_filter,
    process_query,
)

# ── LLM ──────────────────────────────────────────────────────────────────────

llm = ChatOpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
    base_url="https://api.deepseek.com",
    model="deepseek-chat",
    temperature=0.7,
)

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
        "Authorization": f"Bearer {os.environ.get('LANGSEARCH_API_KEY', '')}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()
    data = response.json()
    return [r["relevance_score"] for r in data["results"]]


# ── BM25 index (lazy, session-level cache) ────────────────────────────────────

_bm25_index: BM25Okapi | None = None
_bm25_raw_docs: list | None = None  # list of {"page_content": str, "metadata": dict}


def _load_bm25(db) -> tuple[BM25Okapi, list]:
    """Fetch all Chroma documents once and build a BM25 index (cached)."""
    global _bm25_index, _bm25_raw_docs
    if _bm25_index is not None and _bm25_raw_docs is not None:
        return _bm25_index, _bm25_raw_docs

    print("[BM25] Building index from Chroma (first call only) …")
    result = db.get(include=["documents", "metadatas"])
    texts: list[str] = result["documents"]
    metas: list[dict] = result["metadatas"]

    tokenized = [t.lower().split() for t in texts]
    _bm25_index = BM25Okapi(tokenized)
    _bm25_raw_docs = [
        {"page_content": t, "metadata": m} for t, m in zip(texts, metas)
    ]
    print(f"[BM25] Index ready — {len(_bm25_raw_docs)} documents")
    return _bm25_index, _bm25_raw_docs


# ── Individual retrieval paths ────────────────────────────────────────────────

def _bm25_retrieve(query: str, db, k: int = 10) -> list[Document]:
    index, all_docs = _load_bm25(db)
    scores = index.get_scores(query.lower().split())
    top_idx = np.argsort(scores)[::-1][:k]
    return [
        Document(
            page_content=all_docs[i]["page_content"],
            metadata=all_docs[i]["metadata"],
        ) 
        for i in top_idx if scores[i] > 0
    ]


def _dense_retrieve(
    query: str, db, k: int = 10, year_filter: dict | None = None
) -> list[Document]:
    if year_filter:
        return db.similarity_search(query, k=k, filter=year_filter)
    return db.similarity_search(query, k=k)


def _hyde_retrieve(query: str, db, k: int = 10) -> list[Document]:
    """Embed a hypothetical answer and search the existing Chroma index."""
    hypothesis = generate_hyde_hypothesis(query)
    hyp_vec = embeddings.embed_query(hypothesis)
    return db.similarity_search_by_vector(hyp_vec, k=k)


def _metadata_retrieve(query: str, db, k: int = 10) -> list[Document]:
    """
    TF-IDF similarity between the query and each chunk's section_summary metadata.
    Returns the top-k chunks whose summaries best match the query.
    """
    _, all_docs = _load_bm25(db)

    # Use section_summary if present, else fall back to page_content
    summaries = [
        d["metadata"].get("section_summary") or d["page_content"]
        for d in all_docs
    ]

    non_empty = [(i, s) for i, s in enumerate(summaries) if s and s.strip()]
    if not non_empty:
        return []

    indices, texts = zip(*non_empty)
    corpus = list(texts) + [query]
    tfidf = TfidfVectorizer(stop_words="english").fit_transform(corpus)
    sims = sklearn_cosim(tfidf[-1], tfidf[:-1])[0]

    top_local = np.argsort(sims)[::-1][:k]
    return [
        Document(
            page_content=all_docs[indices[i]]["page_content"],
            metadata=all_docs[indices[i]]["metadata"],
        )
        for i in top_local
        if sims[i] > 0
    ]


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
    k_per_path: int = 10,
    k_final: int = 5,
    year_hint: int | None = None,
    enable_hyde: bool = True,
    enable_metadata: bool = True,
    enable_expansion: bool = True,
) -> list[Document]:
    """
    Multi-path Retrieval (FinSage §3.2):
      For each sub-query run BM25 + Dense + HyDE + Metadata retrievers,
      merge and deduplicate, expand chunks, then re-rank.
    """
    seen: dict[str, Document] = {}  # content → doc (deduplication key)

    def _add(retrieved: list[Document]) -> None:
        for d in retrieved:
            if d.page_content not in seen:
                seen[d.page_content] = d

    for sq in sub_queries:
        print(f"[MPR] sub-query: {sq!r}")
        _add(_bm25_retrieve(sq, db, k=k_per_path))
        _add(_dense_retrieve(sq, db, k=k_per_path, year_filter=year_filter))

        if enable_hyde:
            try:
                _add(_hyde_retrieve(sq, db, k=k_per_path))
            except Exception as e:
                print(f"  [HyDE] skipped: {e}")

        if enable_metadata:
            _add(_metadata_retrieve(sq, db, k=k_per_path))

    candidates = list(seen.values())
    print(f"[MPR] candidates after multi-path: {len(candidates)}")

    if enable_expansion:
        candidates = _expand_chunks(candidates, db)
        print(f"[MPR] after chunk expansion: {len(candidates)}")

    # Re-rank anchored on the first (primary) sub-query
    anchor = sub_queries[0] if sub_queries else ""
    final = _rerank(anchor, candidates, k=k_final, year_hint=year_hint)
    print(f"[MPR] final docs after reranking: {len(final)}")
    return final


# ── Answer generation ─────────────────────────────────────────────────────────

_ANSWER_PROMPT = ChatPromptTemplate.from_template("""Answer the user's question based on the following context:
{context}

Question: {input}
""")


def answer_question(question: str) -> dict:
    db = setup_retriever()

    # 1. Process query: extract years, operator, and sub-queries in one LLM call
    processed = process_query(question)
    years: list[int] = processed.get("extracted_years", [])
    operator: str = processed.get("operator", "none")
    sub_queries: list[str] = processed.get("sub_queries", [question])
    year_hint = years[0] if years else None
    year_filter = get_year_filter(years, operator) if years else None

    debug_info = {
        "original_query": question,
        "sub_queries": sub_queries,
        "extracted_years": years,
        "operator": operator,
    }
    print(f"[MPR] sub-queries: {sub_queries}")

    # 3. Multi-path retrieval + re-ranking
    docs = mpr_retrieve(
        sub_queries,
        db,
        year_filter=year_filter,
        k_per_path=10,
        k_final=7,
        year_hint=year_hint,
    )

    # 4. Generate answer
    context = "\n\n".join(d.page_content for d in docs)
    response = llm.invoke(_ANSWER_PROMPT.format(context=context, input=question))

    return {
        "answer": response.content,
        "context": docs,
        "extracted_years": years,
        "debug_info": debug_info,
    }


if __name__ == "__main__":
    result = answer_question("BBCA performance in 2024")
    print(result["answer"])
