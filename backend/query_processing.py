import re
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import streamlit as st

llm = ChatOpenAI(
    api_key=st.secrets['DEEPSEEK_API_KEY'],
    base_url="https://api.deepseek.com",
    model="deepseek-chat",
    temperature=0.7,
)

class QueryResult:
    def __init__(self, extracted_years: list[int], operator: str, sub_queries: list[str]):
        self.extracted_years = extracted_years
        self.operator = operator
        self.sub_queries = sub_queries


def get_year_filter(years: list, operator: str) -> dict:
    """Convert extracted years to vectorstore filter"""
    if not years:
        return {}

    if operator == "exact":
        if len(years) == 1:
            return {"year": years[0]}
        else:
            return {"year": {"$in": years}}
    elif operator == "gte":
        return {"year": {"$gte": years[0]}}
    elif operator == "lte":
        return {"year": {"$lte": years[0]}}
    else:
        return {}


PROCESS_QUERY_PROMPT = ChatPromptTemplate.from_template("""You are a query pre-processor for a financial RAG system. Given a user question, do two things in one step:
1. Extract any year(s) the user is asking about and determine the year filter operator.
2. Decompose the question into 1-3 focused sub-questions suitable for document retrieval.

Current year: 2026

User query: {query}

Output ONLY valid JSON in this exact format:
{{
    "extracted_years": [2025],
    "operator": "exact",
    "sub_queries": [
        "BCA total revenue and net profit 2025",
        "BCA return on equity and assets 2025"
    ]
}}

Rules for extracted_years and operator:
- "exact"  → user asks about specific year(s). Use $in if multiple.
- "gte"    → user asks about a year and onwards (e.g. "since 2023").
- "lte"    → user asks up to a year (e.g. "before 2025").
- "none"   → no year mentioned; set extracted_years to [].

Rules for sub_queries:
- Each sub-question must be self-contained and address a specific aspect.
- Include the year in each sub-question when a year was extracted.
- Use at most 3 sub-questions; 1 is fine for simple queries.
- Use Indonesian Language

Examples:
- Query: "How did BCA perform last year?"
  output: {{"extracted_years": [2025], "operator": "exact", "sub_queries": ["BCA financial performance and revenue 2025", "BCA net profit and margins 2025"]}}
- Query: "Compare BCA 2024 and 2025"
  output: {{"extracted_years": [2024, 2025], "operator": "exact", "sub_queries": ["BCA revenue and profit 2024", "BCA revenue and profit 2025", "BCA year-over-year growth 2024 2025"]}}
- Query: "BCA since 2023"
  output: {{"extracted_years": [2023], "operator": "gte", "sub_queries": ["BCA financial performance 2023 onwards"]}}
- Query: "What are BCA's main risks?"
  output: {{"extracted_years": [], "operator": "none", "sub_queries": ["BCA risk factors", "BCA credit risk and operational risk"]}}
""")


def process_query(query: str) -> QueryResult:
    """Single LLM call: year extraction + operator + query decomposition. 

    Replaces the former preprocess_query + decompose_query pair.

    Returns:
        {
            "extracted_years": list[int],
            "operator": str,   # "exact" | "gte" | "lte" | "none"
            "sub_queries": list[str],
        }
    """
    try:
        response = llm.invoke(PROCESS_QUERY_PROMPT.format(query=query))
        content = str(response.content)
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            sub_queries = data.get("sub_queries", [])
            if not sub_queries:
                sub_queries = [query]
        return QueryResult(
            extracted_years = data.get("extracted_years", []),
            operator = data.get("operator", "none"),
            sub_queries = sub_queries
            )
    except Exception as e:
        print(f"[process_query] Warning: {e}")
    return QueryResult([],"",[query])


HYDE_PROMPT = ChatPromptTemplate.from_template("""Write a short paragraph (3-5 sentences) that reads like an extract from a company financial report and directly answers the following question. Use formal financial language.

Question: {query}

Answer:
Respond in Indonesian.""")


def generate_hyde_hypothesis(query: str) -> str:
    """Generate a hypothetical document that would answer the query (HyDE, FinSage §3.2)."""
    try:
        response = llm.invoke(HYDE_PROMPT.format(query=query))
        return response.content.strip()
    except Exception as e:
        print(f"[HyDE] Warning: {e}")
        return query
