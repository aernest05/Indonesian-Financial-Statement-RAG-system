import json
import os
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from backend.pipeline import answer_question, prepare_retrieval
from backend.llm import stream_answer
from backend.logger import log_query

EXEMPT_IPS = {""}

def rate_limit_key(request: Request) -> str:
    ip = get_remote_address(request)
    # Unique key per request for exempt IPs so they never accumulate in any bucket
    return str(uuid.uuid4()) if ip in EXEMPT_IPS else ip

limiter = Limiter(key_func=rate_limit_key)

app = FastAPI(title="RAG Q&A API")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    body = await request.body()
    try:
        question = json.loads(body).get("question", "")
    except Exception:
        question = ""
    log_query(question=question, user_ref=get_remote_address(request), hit_rate_limit=True)
    return JSONResponse(status_code=429, content={"detail": str(exc)})

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

    user_ref = get_remote_address(request)

    def generate():
        try:
            # Step 1 — retrieval (blocking, run in FastAPI's thread pool)
            history = [m.model_dump() for m in body.chat_history]
            retrieval = prepare_retrieval(body.question, history)

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
            answer_chunks: list[str] = []
            for chunk in stream_answer(body.question, retrieval, history):
                if chunk:
                    answer_chunks.append(chunk)
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"

            # Step 3 — log and signal completion
            tickers = {d.metadata.get("ticker", "") for d in retrieval["docs"] if d.metadata.get("ticker")}
            log_query(
                question=body.question,
                response_preview="".join(answer_chunks),
                ticker=", ".join(sorted(tickers)),
                user_ref=user_ref,
            )
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

@app.get("/stocks")
def list_stocks():
    """Return the list of stocks available in the RAG database."""
    import pathlib
    report_dates_path = pathlib.Path("report_dates.json")
    all_companies_path = pathlib.Path("data/allCompanies.json")

    with open(report_dates_path) as f:
        report_dates: dict = json.load(f)

    tickers = sorted({key.split("_")[0].strip().rstrip(" (1)") for key in report_dates})
    # Normalise any "(1)" suffixes that appear in filenames
    tickers = sorted({t.split(" ")[0] for t in tickers})

    with open(all_companies_path) as f:
        companies: list[dict] = json.load(f)["data"]

    company_map = {c["KodeEmiten"]: c for c in companies}

    result = []
    for ticker in tickers:
        info = company_map.get(ticker, {})
        result.append({
            "ticker": ticker,
            "name": info.get("NamaEmiten", ticker),
            "sector": info.get("Sektor", ""),
            "subsector": info.get("SubSektor", ""),
        })

    return result


@app.post("/testlimiter")
@limiter.limit("5/hour")
def testlimiter(request: Request):
    return {"status": "ok", "message": "Rate limit test passed"}
