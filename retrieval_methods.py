from query_processing import generate_hyde_hypothesis
from rank_bm25 import BM25Okapi
from langchain_core.documents import Document

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
    hyp_vec = db._embedding_function.embed_query(hypothesis)
    return db.similarity_search_by_vector(hyp_vec, k=k)


def _metadata_retrieve(query: str, db, k: int = 10) -> list[Document]:
    """
    TF-IDF similarity between the query and each chunk's section_summary metadata.
    Returns the top-k chunks whose summaries best match the query.
    """
    from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosim
    from sklearn.feature_extraction.text import TfidfVectorizer
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
