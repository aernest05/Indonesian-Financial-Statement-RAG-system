from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import os
import re


def setup_retriever(chroma_db_dir: str = "chroma_langchain_db"):
    """Initialize embeddings and create retriever """
    # Load or create database
    print(chroma_db_dir)
    embeddings = GoogleGenerativeAIEmbeddings(
                api_key=os.environ.get("GEMINI_API_KEY_PERSONAL",""), ## ignore
                model="gemini-embedding-2-preview"
            )
    
    db = Chroma(
        persist_directory= chroma_db_dir,
        embedding_function=embeddings,
    )
    return db


SECTION_MAP = {
    "4220000": "balance_sheet",
    "4322000": "income_statement",
    "4510000": "cash_flow",
    "4610000": "accounting_policy",
    "4631100": "notes_interest_income",
    "4632100": "notes_interest_expense",
    "4613100": "notes_loans",
}


def _classify_section(section_id):
    for key, val in SECTION_MAP.items():
        if section_id.startswith(key[:5]):
            return val
    return "other"


def _parse_filename(file_path):
    # FinancialStatement-2024-II-BBCA.pdf
    name = file_path.split("/")[-1].replace(".pdf", "")
    parts = name.split("-")

    period_map = {"I": "Q1", "II": "Q2", "III": "Q3", "Tahunan": "Annual"}

    return {
        "year": int(parts[1]),
        "period": period_map.get(parts[2], parts[2]),
        "ticker": parts[3],
        "source": file_path,
    }


def split_documents(file_path):
    loader = PyPDFLoader(file_path)
    pages = loader.load()
    file_meta = _parse_filename(file_path)

    # Combine all pages into one text
    full_text = "\n".join([p.page_content for p in pages])

    # Split by XBRL section headers
    pattern = r'(\[\d{7}[^\]]*\])'
    parts = re.split(pattern, full_text)

    docs = []
    for i in range(1, len(parts), 2):
        section_id_raw = parts[i].strip("[]")
        content = parts[i+1].strip() if i+1 < len(parts) else ""

        if not content:
            continue

        section_type = _classify_section(section_id_raw)

        # Build embed-friendly text
        embed_text = f"""
Ticker: {file_meta['ticker']}
Year: {file_meta['year']} | Period: {file_meta['period']}
Section: {section_type}
---
{content}
""".strip()

        metadata = {
            **file_meta,
            "section_id": section_id_raw,
            "section_type": section_type,
        }

        docs.append(Document(page_content=embed_text, metadata=metadata))

    return docs


def embed_documents(file_path,chroma_db_dir: str = "chroma_langchain_db" ,apply_ffp: bool = False):
    """Embed new documents and store in vector database.

    When apply_ffp=True the Financial Filings Pre-processing pipeline
    (FinSage §3.1) is run before embedding:
    1. Near-duplicate chunk removal (TF-IDF cosine similarity)
    2. Co-reference resolution (LLM replaces pronouns with antecedents)
    3. Section-summary metadata generation (LLM summarises each page)
    """
    chunks = split_documents(file_path)

    db = setup_retriever(chroma_db_dir)

    db.add_documents(chunks)

if __name__ == "__main__":
    db_name = "financial_statements_db"
    db = setup_retriever(db_name)
    data = db.get(include=["metadatas", "documents"])

    existing_sources = {metadata['source'] for metadata in data['metadatas']} if data else []

    folder = "./data/banks"
    for file in os.listdir(folder):
        file_path = folder+"/"+file
        if file_path in existing_sources:
            print(f'{file} already exist')
        else:
            print(f"embedding {file}...")
            embed_documents(file_path, db_name, False)
            print("Done")
