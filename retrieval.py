from langchain_openai import ChatOpenAI
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains.retrieval import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate
import os
from ingestion import setup_retriever
from query_processing import retrieve_with_preprocessing


# Initialize the LLM
llm = ChatOpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"), 
    base_url="https://api.deepseek.com",
    model="deepseek-chat",  # Specify DeepSeek model
    temperature=0.7)

prompt = ChatPromptTemplate.from_template("""
Answer the user's question based on the following context:
{context}

Question: {input}
""")

def answer_question(question: str):
    db = setup_retriever()
    retriever = db.as_retriever(k=8)
    """Query the retrieval chain with a question."""
    docs, extracted_years, debug_info = retrieve_with_preprocessing(
        question, 
        retriever,
        vectorstore=db  # Pass the vectorstore for filtering
    )

    context = "\n\n".join([doc.page_content for doc in docs])
    
    # Get answer from LLM
    response = llm.invoke(prompt.format(context=context, input=question))
    print(response)
    
    return {
        "answer": response.content,
        "context": docs,
        "extracted_years": extracted_years,
        "debug_info": debug_info
    }


if __name__ == "__main__":
    # Example usage
    raw_query = "BBCA performance in 2023"
    answer_question("BBCA performance in 2023")