import streamlit as st
from retrieval import answer_question
import os

# Initialize session state for question
if "user_question" not in st.session_state:
    st.session_state.user_question = ""

# Quick prompt functions
def set_prompt(prompt_text):
    st.session_state.user_question = prompt_text

# Page configuration
st.set_page_config(
    page_title="RAG Q&A System",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title and description
st.title("🔍 RAG Q&A System")
st.markdown("Ask questions about your documents and get AI-powered answers backed by your data.")

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    st.info(
        "This system uses Google Gemini LLM with your document database for retrieval-augmented generation."
    )
    
    # Check if API key is set
    if not os.environ.get("GEMINI_API_KEY_PERSONAL"):
        st.warning("⚠️ GEMINI_API_KEY_PERSONAL environment variable not set")
    else:
        st.success("✅ API Key configured")

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📝 Question Input")
    
    # Quick prompt buttons
    st.markdown("**⚡ Quick Prompts:**")
    qp_col1, qp_col2, qp_col3 = st.columns(3)

    with qp_col1:
        if st.button("📄 BCA performance 2024"):
            set_prompt("BCA performance 2024")

    with qp_col2:
        if st.button("⚠️ Identify Key Risks"):
            set_prompt("What are the main risks mentioned in the document?")

    with qp_col3:
        if st.button("📊 Extract Key Metrics"):
            set_prompt("What are the important financial or performance metrics?")
    
    # Text input for user query
    user_question = st.text_area(
        "Enter your question:",
        value=st.session_state.user_question,
        placeholder="e.g., What are the main features of the product?",
        height=100,
        key="user_question",
        label_visibility="collapsed"
    )

with col2:
    st.subheader("🎯 Options")
    
    # Additional options
    show_context = st.checkbox("Show retrieved context", value=True)
    auto_scroll = st.checkbox("Auto scroll to results", value=True)

# Submit button
if st.button("🚀 Get Answer", type="primary", use_container_width=True):
    if not st.session_state.user_question.strip():
        st.error("Please enter a question")
    else:
        with st.spinner("🔄 Processing your question..."):
            try:
                # Get response from RAG chain
                response = answer_question(st.session_state.user_question)
                
                
                # Display results
                st.success("✅ Answer generated successfully!")
                
                # Main answer
                st.subheader("💡 Answer")
                st.markdown(response.get("answer", "No answer generated"))
                
                # Show context if requested
                if show_context and "context" in response:
                    with st.expander("📚 Retrieved Context Documents"):
                        context_docs = response.get("context", [])
                        if context_docs:
                            for i, doc in enumerate(context_docs, 1):
                                st.markdown(f"**Document {i}:**")
                                st.text(
                                    doc.page_content[:500] + "..."
                                    if len(doc.page_content) > 500
                                    else doc.page_content
                                )
                                if doc.metadata:
                                    st.caption(f"Metadata: {doc.metadata}")
                        else:
                            st.info("No context documents retrieved")
                            
            except Exception as e:
                st.error(f"❌ Error processing question: {str(e)}")
                st.error("Please check your API key and database connection")

# Footer
st.divider()
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 0.8em;'>
    RAG System powered by LangChain + Google Gemini + Chroma DB
    </div>
    """,
    unsafe_allow_html=True
)

# Session state for history (optional)
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []