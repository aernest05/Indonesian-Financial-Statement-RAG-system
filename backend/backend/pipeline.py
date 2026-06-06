"""MPR pipeline orchestration: retrieval, prepare, and answer entry points."""

import asyncio
from langchain_core.documents import Document

from backend.ingestion import setup_retriever
from backend.query_processing import get_year_filter, process_query
from backend.retrieval_methods import (
    _hyde_retrieve,
    _bm25_retrieve,
    _metadata_retrieve,
    _dense_retrieve,
)
from backend.reranker import rerank
from backend.chunk_bundler import expand_chunks
from backend.llm import stream_answer


async def mpr_retrieve(
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

    async def retrieve_sub_query(sq: str, i: int) -> list[Document]:
        seen: dict[str, Document] = {}

        def _add(retrieved: list[Document]) -> None:
            for d in retrieved:
                if d.page_content not in seen:
                    seen[d.page_content] = d

        print(f"[MPR] sub-query: {sq!r}")

        tasks = [_dense_retrieve(sq, db, k=k_per_retrieval_method, year_filter=year_filter)]

        if enable_bm25_retrieve:
            tasks.append(_bm25_retrieve(sq, db, k=k_per_retrieval_method))
        if enable_hyde:
            tasks.append(_hyde_retrieve(sq, db, k=k_per_retrieval_method))
        if enable_metadata:
            tasks.append(_metadata_retrieve(sq, db, k=k_per_retrieval_method))

        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                _add(result)
            except Exception as e:
                print(f"  [retrieval] skipped: {e}")

        candidates = list(seen.values())
        print(f"[MPR] candidates for SQ{i + 1} after multi-path: {len(candidates)}")

        if enable_expansion:
            candidates = expand_chunks(candidates, db)
            print(f"[MPR] after chunk expansion: {len(candidates)}")

        candidates = rerank(sq, candidates, k=k_per_queries, year_hint=year_hint)
        print(f"[MPR] candidates for SQ{i + 1} after reranking: {len(candidates)}")
        return candidates

    asyncio_results = await asyncio.gather(
        *[retrieve_sub_query(sq, i) for i, sq in enumerate(sub_queries)],
        return_exceptions=True,
    )

    final: list[Document] = []
    for i, result in enumerate(asyncio_results):
        if isinstance(result, Exception):
            print(f"  [MPR] sub-query {i + 1} failed: {result}")
        else:
            final += result
    return final


def prepare_retrieval(question: str, chat_history: list[dict] | None = None) -> dict:
    """Run DB setup, query processing, and MPR retrieval."""
    import time

    t0 = time.perf_counter()
    db = setup_retriever()
    t_db = time.perf_counter()

    processed = process_query(question, chat_history)
    years: list[int] = processed.extracted_years
    operator: str = processed.operator
    sub_queries: list[str] = processed.sub_queries
    year_hint = years[0] if years else None
    year_filter = get_year_filter(years, operator) if years else None
    t_query = time.perf_counter()

    print(f"[MPR] sub-queries: {sub_queries}")

    docs = asyncio.run(mpr_retrieve(
        sub_queries,
        db,
        year_filter=year_filter,
        year_hint=year_hint,
        enable_bm25_retrieve=False,
        enable_metadata=False,
        enable_hyde=True,
        enable_expansion=False,
    ))
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
