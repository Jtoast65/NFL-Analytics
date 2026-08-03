"""
Embed generated documents with OpenAI and upsert them into the `documents`
table (pgvector). Idempotent: re-running refreshes content + embeddings via
ON CONFLICT (doc_type, ref_id).

Usage: python rag/embed_store.py            # embed + store all documents
       python rag/embed_store.py --limit 50 # smoke test on a subset
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pgvector.psycopg2 import register_vector

from rag.build_documents import generate_documents

load_dotenv()
DB_URL = os.environ["DATABASE_URL"]

EMBED_MODEL = "text-embedding-3-small"   # 1536 dims — matches schema/rag.sql
EMBED_BATCH = 200                         # docs per OpenAI embeddings request
_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)


def _chunk(docs: list[dict]) -> list[dict]:
    """Split any long docs; most stay single-chunk. Chunk suffix keeps ref_id unique."""
    out = []
    for d in docs:
        pieces = _splitter.split_text(d["content"])
        if len(pieces) == 1:
            out.append(d)
        else:
            for i, piece in enumerate(pieces):
                out.append({**d, "ref_id": f"{d['ref_id']}#{i}", "content": piece})
    return out


def run(limit: int | None = None) -> None:
    docs = generate_documents()
    if limit:
        docs = docs[:limit]
    docs = _chunk(docs)
    print(f"Embedding {len(docs):,} documents with {EMBED_MODEL} ...")

    embedder = OpenAIEmbeddings(model=EMBED_MODEL)

    conn = psycopg2.connect(DB_URL)
    register_vector(conn)
    total = 0
    with conn:
        with conn.cursor() as cur:
            for i in range(0, len(docs), EMBED_BATCH):
                batch = docs[i:i + EMBED_BATCH]
                vectors = embedder.embed_documents([d["content"] for d in batch])
                rows = [
                    (d["doc_type"], d["ref_id"], d["content"], v,
                     psycopg2.extras.Json(d["metadata"]))
                    for d, v in zip(batch, vectors)
                ]
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO documents (doc_type, ref_id, content, embedding, metadata)
                    VALUES %s
                    ON CONFLICT (doc_type, ref_id)
                    DO UPDATE SET content = EXCLUDED.content,
                                  embedding = EXCLUDED.embedding,
                                  metadata = EXCLUDED.metadata
                    """,
                    rows,
                    template="(%s, %s, %s, %s, %s)",
                    page_size=EMBED_BATCH,
                )
                total += len(batch)
                print(f"  {total:,} / {len(docs):,}", end="\r")
    conn.close()
    print(f"\nDone. Upserted {total:,} document embeddings.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run(args.limit)
