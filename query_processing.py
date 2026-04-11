import re
import os
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"), 
    base_url="https://api.deepseek.com",
    model="deepseek-chat",  # Specify DeepSeek model
    temperature=0.7)

def preprocess_query(query):
    QUERY_PROCESSING_PROMPT = ChatPromptTemplate.from_template("""
    You are a query pre-processor for a RAG system. Your job is to:
    1. Extract the year(s) the user is asking about
    2. Rewrite the query to be more specific for retrieval

    Current year: 2026

    User query: {query}

    Output ONLY valid JSON in this format:
    {{
        "extracted_years": [2025],
        "rewritten_query": "BCA financial performance 2025 revenue profit assets",
        "operator": "exact"  // one of: "exact", "range", "gte", "lte", "none"
    }}

    Examples:
    - Query: "How did BCA perform last year?" → {{"extracted_years": [2025], "rewritten_query": "BCA financial performance 2025", "operator": "exact"}}
    - Query: "BCA Q4 results" → {{"extracted_years": [2025], "rewritten_query": "BCA Q4 fourth quarter results 2025", "operator": "exact"}}
    - Query: "Compare 2024 and 2025 BCA" → {{"extracted_years": [2024, 2025], "rewritten_query": "BCA compare 2024 2025 financial performance", "operator": "exact"}}
    - Query: "BCA since 2023" → {{"extracted_years": [2023], "rewritten_query": "BCA financial performance", "operator": "gte"}}
    - Query: "What is BCA's performance in 2025?" → {{"extracted_years": [2025], "rewritten_query": "BCA financial performance 2025", "operator": "exact"}}
    """)

    response = llm.invoke(QUERY_PROCESSING_PROMPT.format(query=query))
    try:
        # Extract JSON from markdown code blocks if present
        content = response.content
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except:
        pass
    
    # Fallback
    return {"extracted_years": [], "rewritten_query": query, "operator": "none"}

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

def retrieve_with_preprocessing(user_query: str, retriever, vectorstore=None):
    """Full pipeline: preprocess → filter → retrieve"""
    
    # Step 1: Preprocess query
    processed = preprocess_query(user_query)
    rewritten_query = processed.get("rewritten_query", user_query)
    extracted_years = processed.get("extracted_years", [])
    operator = processed.get("operator", "none")
    
    print(f"Original query: {user_query}")
    print(f"Rewritten query: {rewritten_query}")
    print(f"Extracted years: {extracted_years}")
    debug_info = {
        "original_query": user_query,
        "rewritten_query": rewritten_query,
        "extracted_years": extracted_years,
        "operator": operator
    }
    
    # Step 2: Apply year filter if vectorstore is available
    if vectorstore and extracted_years:
        year_filter = get_year_filter(extracted_years, operator)
        if year_filter:
            # Use filtered search
            docs = vectorstore.similarity_search(
                rewritten_query, 
                k=5, 
                filter=year_filter
            )
            return docs, extracted_years, debug_info
    else:
        # Use standard retriever
        docs = retriever.invoke(rewritten_query)
        return docs, extracted_years,debug_info