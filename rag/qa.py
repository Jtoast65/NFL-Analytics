"""
RAG question-answering: retrieve top-k documents, prompt gpt-4o-mini with them
as grounded context, and return an answer plus source citations.

No agents, no multi-step chains — a single retrieve → prompt → answer pass.
"""
import os
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from rag.retriever import retrieve

load_dotenv()
CHAT_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = (
    "You are an NFL statistics assistant. Answer the user's question using ONLY the "
    "numbered context documents provided. The documents contain season totals, rankings, "
    "game recaps, and leaderboards for NFL seasons 2016-2025.\n"
    "Rules:\n"
    "- Base every fact on the context. Do not use outside knowledge.\n"
    "- If the context does not contain the answer, say so plainly.\n"
    "- Be concise and specific, citing exact numbers.\n"
    "- End with 'Sources: [n]' listing the document numbers you used."
)


@lru_cache(maxsize=1)
def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=CHAT_MODEL, temperature=0)


def _format_context(docs: list[dict]) -> str:
    lines = []
    for i, d in enumerate(docs, 1):
        lines.append(f"[{i}] ({d['doc_type']}) {d['content']}")
    return "\n".join(lines)


def answer_question(question: str, k: int = 8) -> dict:
    """Return {'answer': str, 'sources': [{doc_type, ref_id, snippet, score}]}."""
    docs = retrieve(question, k=k)
    if not docs:
        return {"answer": "No documents are available to answer this question.", "sources": []}

    context = _format_context(docs)
    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", f"Context documents:\n{context}\n\nQuestion: {question}"),
    ]
    resp = _llm().invoke(messages)

    sources = [
        {
            "doc_type": d["doc_type"],
            "ref_id": d["ref_id"],
            "snippet": d["content"][:200],
            "score": round(float(d["score"]), 3),
        }
        for d in docs
    ]
    return {"answer": resp.content, "sources": sources}


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Who had the most rushing yards in 2024?"
    result = answer_question(q)
    print("Q:", q)
    print("A:", result["answer"])
    print("\nSources:")
    for s in result["sources"]:
        print(f"  [{s['score']}] {s['doc_type']}:{s['ref_id']}")
