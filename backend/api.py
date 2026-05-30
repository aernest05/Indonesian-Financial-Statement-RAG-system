import json
import os
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from backend.retrieval import answer_question, prepare_retrieval, stream_answer

EXEMPT_IPS = {""}

def rate_limit_key(request: Request) -> str:
    ip = get_remote_address(request)
    # Unique key per request for exempt IPs so they never accumulate in any bucket
    return str(uuid.uuid4()) if ip in EXEMPT_IPS else ip

limiter = Limiter(key_func=rate_limit_key)

app = FastAPI(title="RAG Q&A API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL"), "http://localhost:5173"],  # Vite dev server
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
@limiter.limit("5/hour")
def ask(request: Request, body: QuestionRequest):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty")
    result = answer_question(body.question)
    return AnswerResponse(
        question=body.question,
        answer=result["answer"],
        extracted_years=result["extracted_years"],
        context=[
            ContextDoc(page_content=d.page_content, metadata=d.metadata)
            for d in result["context"]
        ],
    )


# ── Streaming endpoint (Server-Sent Events) ────────────────────────────────────
@app.post("/stream")
@limiter.limit("5/hour")
def stream(request: Request, body: QuestionRequest):
    """
    SSE stream.  Event sequence:
      1. {"type": "context",  "docs": [...], "extracted_years": [...]}
      2. {"type": "chunk",    "content": "..."}   ×N
      3. {"type": "done"}
      on error:
         {"type": "error",   "message": "..."}
    """
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty")

    def generate():
        try:
            # Step 1 — retrieval (blocking, run in FastAPI's thread pool)
            retrieval = prepare_retrieval(body.question)

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
            history = [m.model_dump() for m in body.chat_history]
            for chunk in stream_answer(body.question, retrieval, history):
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

@app.post("/testlimiter")
@limiter.limit("5/hour")
def testlimiter(request: Request):
    return {"status": "ok", "message": "Rate limit test passed"}
