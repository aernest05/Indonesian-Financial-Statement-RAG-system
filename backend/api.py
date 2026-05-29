import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from backend.retrieval import answer_question, prepare_retrieval, stream_answer

app = FastAPI(title="RAG Q&A API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/pdfs", StaticFiles(directory="data"), name="pdfs")


class ChatMessage(BaseModel):
    role: str
    content: str


class QuestionRequest(BaseModel):
    question: str
    chat_history: list[ChatMessage] = []


class ContextDoc(BaseModel):
    page_content: str
    metadata: dict


class AnswerResponse(BaseModel):
    question: str
    answer: str
    extracted_years: list[int]
    context: list[ContextDoc]


# ── Non-streaming endpoint (kept for compatibility) ───────────────────────────
@app.post("/answer", response_model=AnswerResponse)
def ask(request: QuestionRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty")
    result = answer_question(request.question)
    return AnswerResponse(
        question=request.question,
        answer=result["answer"],
        extracted_years=result["extracted_years"],
        context=[
            ContextDoc(page_content=d.page_content, metadata=d.metadata)
            for d in result["context"]
        ],
    )


# ── Streaming endpoint (Server-Sent Events) ────────────────────────────────────
@app.post("/stream")
def stream(request: QuestionRequest):
    """
    SSE stream.  Event sequence:
      1. {"type": "context",  "docs": [...], "extracted_years": [...]}
      2. {"type": "chunk",    "content": "..."}   ×N
      3. {"type": "done"}
      on error:
         {"type": "error",   "message": "..."}
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty")

    def generate():
        try:
            # Step 1 — retrieval (blocking, run in FastAPI's thread pool)
            retrieval = prepare_retrieval(request.question)

            # Send context metadata as the first event so the UI can show
            # source documents immediately, before the LLM starts talking.
            context_event = {
                "type": "context",
                "docs": [
                    {"page_content": d.page_content, "metadata": d.metadata}
                    for d in retrieval["docs"]
                ],
                "extracted_years": retrieval["extracted_years"],
            }
            yield f"data: {json.dumps(context_event, ensure_ascii=False)}\n\n"

            # Step 2 — stream LLM tokens
            history = [m.model_dump() for m in request.chat_history]
            for chunk in stream_answer(request.question, retrieval, history):
                if chunk:
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"

            # Step 3 — signal completion
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering if proxied
            "Connection": "keep-alive",
        },
    )
