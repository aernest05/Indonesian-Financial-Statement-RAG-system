from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
import os

embeddings = GoogleGenerativeAIEmbeddings(
        api_key=os.environ.get("GEMINI_API_KEY_PERSONAL"), ## ignore
        model="gemini-embedding-2-preview"
    )

def split_documents(file_path):
    loader = PyPDFLoader(file_path)
    documents = loader.load()

    for doc in documents:
        meta = doc.metadata
        source_parts = meta["source"].split("-")
        meta["year"] = int(source_parts[1])

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = 800
    )
    return text_splitter.split_documents(documents)

def embed_documents(file_path):
    """Embed new documents and store in vector database."""
    documents = split_documents(file_path)

    db = Chroma(
        persist_directory="chroma_langchain_db",
        embedding_function=embeddings,
    )
    db.add_documents(documents)

def setup_retriever():
    """Initialize embeddings and create retriever (internal)."""
    # Load or create database
    db = Chroma(
        persist_directory="chroma_langchain_db",
        embedding_function=embeddings,
    )
    return db


