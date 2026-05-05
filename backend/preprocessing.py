import os
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    model="deepseek-chat",
    temperature=0.3,
)

DEDUP_THRESHOLD = 0.7
COREF_K = 4
PRONOUNS = {"we", "our", "it", "its", "they", "their", "he", "his", "she", "her"}

# ── Prompts ──────────────────────────────────────────────────────────────────

COREF_PROMPT = ChatPromptTemplate.from_template(
    """You are a language model assistant. Your task is to enhance the given text by replacing ambiguous or context-dependent words with more specific and clear alternatives, based on the context of company's financial reports.

## Here are some guidelines for replacements:
- Replace pronouns like "we" with the appropriate entity, but only use entities that appear in the current context
- When replacing "it" or other pronouns, use specific names/entities that were previously mentioned in the same or immediately preceding paragraph
- For product references, only use exact product names that appear in the text; if unclear, use general terms like "the vehicle", "this model"
- Do not introduce new entities or products that aren't in the source text

Reference context (preceding chunks from the same section):
{context}

Target text to resolve:
{text}

Return only the resolved text, nothing else.
Translate to Indonesian."""
)

SUMMARY_PROMPT = ChatPromptTemplate.from_template(
    """Summarize the following section from a financial document in 2-3 concise sentences. Focus on the key topics and data points covered.

Section text:
{text}

Summary:
Respond in Indonesian."""
)


# ── Step 1: Deduplication ─────────────────────────────────────────────────────

def deduplicate_chunks(chunks):
    """Remove near-duplicate chunks using TF-IDF cosine similarity (threshold={DEDUP_THRESHOLD})."""
    if len(chunks) <= 1:
        return chunks

    texts = [c.page_content for c in chunks]
    tfidf = TfidfVectorizer().fit_transform(texts)

    keep = [True] * len(chunks)
    for i in range(len(chunks)):
        if not keep[i]:
            continue
        sims = cosine_similarity(tfidf[i], tfidf[i + 1 :])[0]
        for offset, sim in enumerate(sims):
            j = i + 1 + offset
            if keep[j] and sim >= DEDUP_THRESHOLD:
                keep[j] = False

    kept = [c for c, k in zip(chunks, keep) if k]
    removed = len(chunks) - len(kept)
    if removed:
        print(f"  [dedup] Removed {removed} duplicate chunk(s)")
    return kept


# ── Step 2: Co-reference resolution ──────────────────────────────────────────

def _has_pronouns(text: str) -> bool:
    words = set(re.findall(r"\b\w+\b", text.lower()))
    return bool(words & PRONOUNS)


def resolve_coreferences(chunks):
    """
    Replace pronouns in each chunk with their antecedents using up to
    COREF_K preceding chunks from the same page as context.
    Skips chunks that contain no pronouns to avoid unnecessary LLM calls.
    """
    for i, chunk in enumerate(chunks):
        if not _has_pronouns(chunk.page_content):
            continue

        current_page = chunk.metadata.get("page")
        preceding_texts = []
        for j in range(max(0, i - COREF_K), i):
            if chunks[j].metadata.get("page") == current_page:
                preceding_texts.append(chunks[j].page_content)

        if not preceding_texts:
            continue

        context = "\n---\n".join(preceding_texts)
        try:
            response = llm.invoke(
                COREF_PROMPT.format(context=context, text=chunk.page_content)
            )
            chunk.page_content = response.content.strip()
        except Exception as e:
            print(f"  [coref] Warning: chunk {i} skipped ({e})")

    return chunks


# ── Step 3: Metadata / section-summary generation ────────────────────────────

def generate_metadata_summaries(chunks):
    """
    Group chunks by page (used as a proxy for document section), generate
    one summary per page, and append it to every chunk's metadata as
    'section_summary'.
    """
    # Build page → chunk index
    page_groups: dict[int, list[int]] = {}
    for idx, chunk in enumerate(chunks):
        page = chunk.metadata.get("page", 0)
        page_groups.setdefault(page, []).append(idx)

    for page, indices in page_groups.items():
        combined = "\n".join(chunks[i].page_content for i in indices)[:3000]
        try:
            response = llm.invoke(SUMMARY_PROMPT.format(text=combined))
            summary = response.content.strip()
        except Exception as e:
            print(f"  [summary] Warning: page {page} skipped ({e})")
            summary = ""

        for i in indices:
            chunks[i].metadata["section_summary"] = summary

    return chunks


# ── Public entry point ────────────────────────────────────────────────────────

def run_ffp_pipeline(chunks, apply_coref: bool = True, apply_summaries: bool = True):
    """
    Financial Filings Pre-processing (FFP) pipeline (FinSage §3.1).

    Steps applied in order:
      1. Redundant chunk de-duplication
      2. Co-reference resolution   (optional, costs LLM calls)
      3. Metadata summary generation (optional, costs LLM calls)
    """
    print(f"[FFP] Starting with {len(chunks)} chunks")

    chunks = deduplicate_chunks(chunks)
    print(f"[FFP] After deduplication: {len(chunks)} chunks")

    if apply_coref:
        print("[FFP] Running co-reference resolution …")
        chunks = resolve_coreferences(chunks)

    if apply_summaries:
        print("[FFP] Generating section summaries …")
        chunks = generate_metadata_summaries(chunks)

    print(f"[FFP] Pipeline complete — {len(chunks)} chunks ready for embedding")
    return chunks
