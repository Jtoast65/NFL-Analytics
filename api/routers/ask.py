"""RAG Q&A endpoint — natural-language questions over the NFL database."""
from fastapi import APIRouter, HTTPException

from api.schemas import AskRequest, AskResponse
from rag.qa import answer_question

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    """
    Retrieve the most relevant NFL stat documents and answer the question with
    gpt-4o-mini, grounded strictly in the retrieved context. Returns the answer
    plus the source documents used.
    """
    try:
        result = answer_question(req.question, k=req.k)
    except Exception as e:  # OpenAI / DB errors surface as 502
        raise HTTPException(status_code=502, detail=f"Q&A backend error: {e}")
    return AskResponse(**result)
