# FinSage — Indonesian Financial Report Intelligence

**Live demo:** [indofsrag.streamlit.app](https://indofsrag.streamlit.app/)

FinSage is a Retrieval-Augmented Generation (RAG) system for querying Indonesian public company financial reports in natural language. Ask questions about revenue, profit, balance sheet items, risk factors, and more — and get answers grounded in the actual filings.

> **Current data coverage: BCA,BRI,MANDIRI,BNI**
> Support for additional Indonesian stocks (IDX-listed companies) is actively in development and will be rolled out in the near future.

---

## Features

- **Natural language queries** — ask in Indonesian or English
- **Multi-path retrieval (MPR)** — combines dense vector search, BM25 sparse retrieval, HyDE (hypothetical document embeddings), and metadata retrieval
- **Query decomposition** — complex questions are automatically split into focused sub-queries
- **Year-aware filtering** — queries like "since 2023" or "compare 2024 and 2025" are parsed into precise metadata filters
- **Cross-encoder reranking** — results are reranked via LangSearch before answer generation
- **Streaming answers** — responses stream token-by-token in the UI

## Tech Stack

| Component | Technology |
|---|---|
| Frontend | Streamlit |
| LLM | DeepSeek (`deepseek-chat`) |
| Embeddings | Google Gemini (`gemini-embedding-2-preview`) |
| Vector store | ChromaDB |
| Reranker | LangSearch |
| Retrieval framework | LangChain |

## Project Structure

```
├── app.py                    # Streamlit frontend
├── backend/
│   ├── ingestion.py          # PDF ingestion and ChromaDB setup
│   ├── preprocessing.py      # Document chunking and metadata extraction
│   ├── query_processing.py   # Query decomposition and year extraction
│   ├── retrieval.py          # MPR pipeline and answer generation
│   ├── retrieval_methods.py  # BM25, dense, HyDE, metadata retrievers
│   └── api.py                # API layer
└── .streamlit/
    └── secrets.toml          # API keys (not committed)
```

## Local Setup

1. Clone the repo and install dependencies:

```bash
pip install -r requirements.txt
```

2. Create `.streamlit/secrets.toml` with your API keys:

```toml
DEEPSEEK_API_KEY = "..."
GEMINI_API_KEY_PERSONAL = "..."
LANGSEARCH_API_KEY = "..."
```

3. Run the app:

```bash
streamlit run app.py
```

## Roadmap

- [ ] Add more IDX-listed stocks (BBRI, BMRI, TLKM, and others)
- [ ] Multi-company comparative queries
- [ ] Automatic ingestion pipeline for new filings
