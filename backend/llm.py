"""Shared LLM singleton, answer prompt, and streaming."""

import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

_llm_cache: dict[float, ChatOpenAI] = {}


def _get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """Lazy singleton per temperature — avoids redundant DeepSeek connections."""
    if temperature not in _llm_cache:
        _llm_cache[temperature] = ChatOpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            temperature=temperature,
        )
    return _llm_cache[temperature]


_ANSWER_PROMPT = ChatPromptTemplate.from_template("""Answer the user's question based on the following context:
{context}

{chat_history}Question: {input}

Respond in Indonesian.
""")


def stream_answer(question: str, retrieval: dict, chat_history: list[dict] | None = None):
    """Yield LLM answer chunks. Call after prepare_retrieval."""
    import time

    history_str = ""
    if chat_history:
        lines = [
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in chat_history
        ]
        history_str = "Previous conversation:\n" + "\n".join(lines) + "\n\n"

    prompt = _ANSWER_PROMPT.format(
        context=retrieval["context"],
        input=question,
        chat_history=history_str,
    )
    for chunk in _get_llm().stream(prompt):
        yield chunk.content

    t_llm = time.perf_counter()
    retrieval["timings"]["llm_s"] = round(t_llm - retrieval["_t_retrieval"], 2)
    retrieval["timings"]["total_s"] = round(t_llm - retrieval["_t0"], 2)
