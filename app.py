import streamlit as st
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.retrieval import prepare_retrieval, stream_answer

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    # Each entry: {"role": "user"|"assistant", "content": str, "retrieval": dict|None}
    st.session_state.messages = []

if "user_question" not in st.session_state:
    st.session_state.user_question = ""

def set_prompt(text: str):
    st.session_state.user_question = text

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FinSage — Financial Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* Base */
    [data-testid="stAppViewContainer"] { background: #0a0e1a; }
    [data-testid="stHeader"] { background: transparent; }
    section[data-testid="stSidebar"] { background: #0f1525; border-right: 1px solid #1e2a45; }

    /* Typography */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #e2e8f0; }

    /* Hide default streamlit chrome */
    #MainMenu, footer { visibility: hidden; }

    /* Hero */
    .hero { padding: 2.5rem 0 1.5rem; }
    .hero h1 {
        font-size: 2.6rem; font-weight: 700; letter-spacing: -0.5px;
        background: linear-gradient(135deg, #60a5fa, #a78bfa);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
    }
    .hero p { color: #64748b; font-size: 1rem; margin: 0; }

    /* Quick prompt chips */
    div[data-testid="column"] button {
        background: #111827 !important;
        border: 1px solid #1e2a45 !important;
        color: #94a3b8 !important;
        border-radius: 999px !important;
        font-size: 0.8rem !important;
        padding: 0.35rem 1rem !important;
        transition: all 0.15s ease !important;
    }
    div[data-testid="column"] button:hover {
        border-color: #3b82f6 !important;
        color: #60a5fa !important;
        background: #0f1a2e !important;
    }

    /* Textarea */
    textarea {
        background: #0f1525 !important;
        border: 1px solid #1e2a45 !important;
        border-radius: 12px !important;
        color: #e2e8f0 !important;
        font-size: 0.95rem !important;
        padding: 0.85rem 1rem !important;
    }
    textarea:focus { border-color: #3b82f6 !important; box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important; }

    /* Primary button */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb, #7c3aed) !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        letter-spacing: 0.3px !important;
        padding: 0.65rem !important;
        color: white !important;
        transition: opacity 0.15s ease !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover { opacity: 0.88 !important; }

    /* Chat messages */
    [data-testid="stChatMessage"] {
        background: #0f1525 !important;
        border: 1px solid #1e2a45 !important;
        border-radius: 12px !important;
        padding: 1rem 1.25rem !important;
        margin: 0.4rem 0 !important;
    }
    [data-testid="stChatMessageContent"] { color: #cbd5e1 !important; font-size: 0.95rem !important; }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: #0f1525;
        border: 1px solid #1e2a45;
        border-radius: 10px;
        padding: 0.75rem 1rem;
    }
    [data-testid="stMetricLabel"] { color: #64748b !important; font-size: 0.75rem !important; }
    [data-testid="stMetricValue"] { color: #60a5fa !important; font-size: 1.3rem !important; font-weight: 600 !important; }

    /* Expanders */
    [data-testid="stExpander"] {
        background: #0f1525 !important;
        border: 1px solid #1e2a45 !important;
        border-radius: 10px !important;
    }

    /* Divider */
    hr { border-color: #1e2a45 !important; }

    /* Status messages */
    [data-testid="stAlert"] { border-radius: 10px !important; }

    /* Chat history section label */
    .history-label {
        color: #334155;
        font-size: 0.7rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 1.5rem 0 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### FinSage")
    st.caption("Financial Intelligence Platform")
    st.divider()

    st.markdown("**Model**")
    st.caption("DeepSeek Chat via OpenAI-compatible API")

    st.markdown("**Retrieval**")
    st.caption("Dense · HyDE · LangSearch Reranker")

    st.divider()
    if not os.environ.get("DEEPSEEK_API_KEY"):
        st.warning("DEEPSEEK_API_KEY not set")
    else:
        st.success("API key configured")

    show_context = st.checkbox("Show source documents", value=True)

    st.divider()
    turn_count = len([m for m in st.session_state.messages if m["role"] == "user"])
    st.caption(f"💬 {turn_count} turn{'s' if turn_count != 1 else ''} in session")
    if st.button("🗑️ Clear chat history", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>FinSage</h1>
  <p>Analyze Indonesian public company financial statements with AI.</p>
</div>
""", unsafe_allow_html=True)

# ── Quick prompts ─────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("BCA performance 2024"):
        set_prompt("How did BCA perform in 2024?")
with c2:
    if st.button("BCA Loan Growth"):
        set_prompt("How has BCA's total loans and deposit growth trended over the years?")
with c3:
    if st.button("Bank Safety Metrics"):
        set_prompt("How safe is BCA over the years? Analyze its CAR, NPL, and LDR ratios.")

# ── Input ─────────────────────────────────────────────────────────────────────
st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
user_question = st.text_area(
    "question",
    value=st.session_state.user_question,
    placeholder="Ask about a company's financials, risks, metrics...",
    height=100,
    key="user_question",
    label_visibility="collapsed",
)

if st.button("Analyze →", type="primary", use_container_width=True):
    question = st.session_state.user_question.strip()
    if not question:
        st.error("Please enter a question first.")
    else:
        try:
            # Snapshot history BEFORE this turn (passed as LLM context)
            prior_history = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ]

            # Persist user message immediately
            st.session_state.messages.append({"role": "user", "content": question, "retrieval": None})

            with st.spinner("Retrieving context from database..."):
                retrieval = prepare_retrieval(question)

            # Stream assistant reply inside a chat bubble
            with st.chat_message("assistant"):
                full_response = st.write_stream(
                    stream_answer(question, retrieval, chat_history=prior_history)
                )

                timings = retrieval.get("timings", {})
                if timings:
                    with st.expander("⏱ Performance"):
                        labels = {
                            "db_setup_s": "DB Setup",
                            "query_processing_s": "Query Processing",
                            "retrieval_s": "Retrieval",
                            "llm_s": "LLM Generation",
                            "total_s": "Total",
                        }
                        cols = st.columns(len(timings))
                        for col, (key, val) in zip(cols, timings.items()):
                            col.metric(labels.get(key) or key, f"{val}s")

                if show_context:
                    docs = retrieval.get("docs", [])
                    if docs:
                        with st.expander(f"📄 Source documents ({len(docs)})"):
                            for i, doc in enumerate(docs, 1):
                                st.markdown(f"**#{i}**")
                                st.text(
                                    doc.page_content[:500] + "…"
                                    if len(doc.page_content) > 500
                                    else doc.page_content
                                )
                                if doc.metadata:
                                    st.caption(str(doc.metadata))
                                st.divider()

            # Save assistant message with retrieval data for re-render
            st.session_state.messages.append({
                "role": "assistant",
                "content": full_response,
                "retrieval": retrieval,
            })

        except Exception as e:
            st.error(f"Something went wrong: {str(e)}")

# ── Chat history ──────────────────────────────────────────────────────────────
if st.session_state.messages:
    st.markdown("<p class='history-label'>Conversation history</p>", unsafe_allow_html=True)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            # Re-render source docs for past assistant turns
            if msg["role"] == "assistant" and show_context and msg.get("retrieval"):
                docs = msg["retrieval"].get("docs", [])
                if docs:
                    with st.expander(f"📄 Source documents ({len(docs)})"):
                        for i, doc in enumerate(docs, 1):
                            st.markdown(f"**#{i}**")
                            st.text(
                                doc.page_content[:500] + "…"
                                if len(doc.page_content) > 500
                                else doc.page_content
                            )
                            if doc.metadata:
                                st.caption(str(doc.metadata))
                            st.divider()

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<p style='text-align:center;color:#1e2a45;font-size:0.75rem;'>"
    "FinSage · LangChain · DeepSeek · ChromaDB"
    "</p>",
    unsafe_allow_html=True,
)
