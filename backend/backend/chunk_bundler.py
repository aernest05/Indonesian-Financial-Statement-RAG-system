"""Chunk bundling: expand retrieved docs with adjacent-page neighbors."""

from langchain_core.documents import Document
from backend.retrieval_methods import _load_bm25


def expand_chunks(docs: list[Document], db) -> list[Document]:
    """
    For each retrieved chunk, add chunks from the same source file on
    adjacent pages (page ± 1). Uses the in-memory BM25 cache to avoid
    extra Chroma queries. (FinSage §3.2 Chunk Bundling)
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
