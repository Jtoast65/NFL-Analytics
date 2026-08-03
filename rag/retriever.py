"""
Cosine top-k retrieval over the `documents` table (pgvector).

Embeds the query with the same OpenAI model used at index time, then orders by
cosine distance (`<=>`). Returns the matched documents with a similarity score.
"""
import os
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from pgvector.psycopg2 import register_vector

load_dotenv()
DB_URL = os.environ["DATABASE_URL"]
EMBED_MODEL = "text-embedding-3-small"


@lru_cache(maxsize=1)
def _embedder() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model=EMBED_MODEL)


def retrieve(question: str, k: int = 6) -> list[dict]:
    """Return the top-k documents most similar to the question."""
    query_vec = _embedder().embed_query(question)

    conn = psycopg2.connect(DB_URL)
    register_vector(conn)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT doc_type, ref_id, content, metadata,
                       1 - (embedding <=> %s::vector) AS score
                FROM documents
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (query_vec, query_vec, k),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


if __name__ == "__main__":
    import json
    q = " ".join(sys.argv[1:]) or "Who had the most rushing yards in 2024?"
    for r in retrieve(q):
        print(f"[{r['score']:.3f}] {r['doc_type']}:{r['ref_id']}")
        print(f"   {r['content'][:160]}...")
    print(json.dumps({"question": q}, indent=2))
