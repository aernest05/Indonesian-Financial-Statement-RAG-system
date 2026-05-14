from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from backend.retrieval import answer_question

app = FastAPI(title="RAG Q&A API")


class QuestionRequest(BaseModel):
    question: str


class ContextDoc(BaseModel):
    page_content: str
    metadata: dict


class AnswerResponse(BaseModel):
    question: str
    answer: str
    extracted_years: list[int]
    context: list[ContextDoc]


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
