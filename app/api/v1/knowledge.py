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


# ── Training Corpus Export ─────────────────────────────────────────


class ExportResponse(BaseModel):
    format: str
    sections: int
    chars: int
    path: str | None = None


@router.get("/export/markdown")
async def export_corpus_markdown() -> dict:
    """Export the full training corpus as structured markdown.

    Returns the complete creative strategy knowledge base as a single
    markdown document, structured for both human reading and ML training.
    """
    from app.knowledge.synthesizer import export_markdown
    md_text = export_markdown()
    return {
        "format": "markdown",
        "content": md_text,
        "chars": len(md_text),
    }


@router.post("/export/markdown/file", response_model=ExportResponse)
async def export_corpus_markdown_file() -> ExportResponse:
    """Export the full training corpus to docs/training_corpus.md."""
    from app.knowledge.synthesizer import export_markdown
    md_text = export_markdown(output_path="docs/training_corpus.md")
    return ExportResponse(
        format="markdown",
        sections=md_text.count("####"),
        chars=len(md_text),
        path="docs/training_corpus.md",
    )


@router.get("/export/training-pairs")
async def export_training_pairs_endpoint() -> dict:
    """Export corpus as (instruction, response) training pairs.

    Returns JSONL-compatible training pairs for fine-tuning.
    Includes DPO pairs (chosen/rejected) where good/bad examples exist.
    """
    from app.knowledge.synthesizer import export_training_pairs
    pairs = export_training_pairs()
    return {
        "format": "training_pairs",
        "count": len(pairs),
        "dpo_pairs": sum(1 for p in pairs if p.get("type") == "dpo_pair"),
        "pairs": pairs,
    }


@router.post("/export/training-pairs/file", response_model=ExportResponse)
async def export_training_pairs_file() -> ExportResponse:
    """Export training pairs to docs/training_pairs.jsonl."""
    from app.knowledge.synthesizer import export_training_pairs
    pairs = export_training_pairs(output_path="docs/training_pairs.jsonl")
    return ExportResponse(
        format="jsonl",
        sections=len(pairs),
        chars=0,
        path="docs/training_pairs.jsonl",
    )


@router.post("/export/system-prompts/files", response_model=ExportResponse)
async def export_system_prompt_fragments() -> ExportResponse:
    """Export domain-specific system prompt fragments to docs/prompts/.

    Each domain gets its own markdown file that can be used as a
    system prompt for custom GPTs, Claude Projects, or any system
    that needs domain expertise.
    """
    from app.knowledge.synthesizer import export_system_prompt_fragments
    fragments = export_system_prompt_fragments(output_path="docs/prompts")
    total_chars = sum(len(v) for v in fragments.values())
    return ExportResponse(
        format="system_prompt_fragments",
        sections=len(fragments),
        chars=total_chars,
        path="docs/prompts/",
    )
