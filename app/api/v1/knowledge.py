"""Knowledge corpus API — ingest, list, update, delete training documents.

POST   /v1/knowledge/ingest           — ingest a new document
GET    /v1/knowledge/corpus           — list all corpus entries
GET    /v1/knowledge/corpus/{slug}    — get a single entry
PUT    /v1/knowledge/corpus/{slug}    — re-ingest / update an entry
DELETE /v1/knowledge/corpus/{slug}    — delete an entry
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.knowledge.doc_ingest.ingester import ingest_document
from app.knowledge.doc_ingest.store import corpus_store

router = APIRouter()


class IngestRequest(BaseModel):
    content: str = Field(..., min_length=50, description="Raw document text (markdown, plain text, or extracted PDF)")
    title: str | None = Field(None, description="Optional title override")
    slug: str | None = Field(None, description="Optional slug override")


class IngestResponse(BaseModel):
    slug: str
    title: str
    version: int
    principles_count: int
    frameworks_count: int
    examples_count: int
    anti_patterns_count: int


class CorpusEntryMeta(BaseModel):
    slug: str
    title: str
    source_summary: str
    version: int
    principles_count: int
    frameworks_count: int
    examples_count: int


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_doc(body: IngestRequest) -> IngestResponse:
    """Ingest a document into the training corpus.

    The document is processed by an LLM to extract principles, frameworks,
    examples, and anti-patterns. The structured result is stored as a
    versioned corpus file.
    """
    entry = await ingest_document(
        content=body.content,
        title=body.title,
        slug=body.slug,
    )
    corpus_store.save(entry)

    return IngestResponse(
        slug=entry.slug,
        title=entry.title,
        version=entry.version,
        principles_count=len(entry.principles),
        frameworks_count=len(entry.frameworks),
        examples_count=len(entry.examples),
        anti_patterns_count=len(entry.anti_patterns),
    )


@router.get("/corpus", response_model=list[CorpusEntryMeta])
async def list_corpus() -> list[dict]:
    """List all corpus entries with metadata."""
    return corpus_store.list_all()


@router.get("/corpus/{slug}")
async def get_corpus_entry(slug: str) -> dict:
    """Get a single corpus entry by slug."""
    entry = corpus_store.get(slug)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Corpus entry '{slug}' not found")
    return entry


@router.put("/corpus/{slug}", response_model=IngestResponse)
async def update_corpus_entry(slug: str, body: IngestRequest) -> IngestResponse:
    """Re-ingest a document, replacing the existing corpus entry."""
    existing = corpus_store.get(slug)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Corpus entry '{slug}' not found")

    entry = await ingest_document(
        content=body.content,
        title=body.title or existing.get("title"),
        slug=slug,
    )
    corpus_store.save(entry)

    return IngestResponse(
        slug=entry.slug,
        title=entry.title,
        version=entry.version,
        principles_count=len(entry.principles),
        frameworks_count=len(entry.frameworks),
        examples_count=len(entry.examples),
        anti_patterns_count=len(entry.anti_patterns),
    )


@router.delete("/corpus/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_corpus_entry(slug: str) -> None:
    """Delete a corpus entry."""
    deleted = corpus_store.delete(slug)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Corpus entry '{slug}' not found")
