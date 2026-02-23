"""Content engine endpoints — generation, drafts, publishing, ingestion."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User

logger = structlog.get_logger()

router = APIRouter(tags=["content"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    platform: str = Field(default="linkedin", pattern="^(linkedin|x)$")
    tone: str = Field(
        default="professional",
        pattern="^(professional|casual|thought_leader)$",
    )
    max_length: int = Field(default=0, ge=0, le=5000)


class IngestRequest(BaseModel):
    text: str = Field(min_length=10, max_length=100000)
    source: str = Field(default="manual", max_length=100)
    title: str = Field(default="", max_length=500)


class PublishRequest(BaseModel):
    post_id: str


# ---------------------------------------------------------------------------
# Generation endpoints
# ---------------------------------------------------------------------------


@router.post("/content/generate")
async def generate_content(
    body: GenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a thought leadership post using RAG + LLM."""
    from app.services.content_engine import generate_post

    return await generate_post(
        db,
        str(user.id),
        topic=body.topic,
        platform=body.platform,
        tone=body.tone,
        max_length=body.max_length,
    )


@router.get("/content/drafts")
async def get_drafts(
    platform: str | None = Query(None, pattern="^(linkedin|x)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all draft posts."""
    from app.services.content_engine import get_drafts as fetch_drafts

    return await fetch_drafts(db, str(user.id), platform=platform)


@router.post("/content/publish")
async def publish_content(
    body: PublishRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Publish a draft post to its target platform."""
    from app.services.content_engine import publish_draft

    try:
        result = await publish_draft(db, str(user.id), body.post_id)
        await db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Knowledge base ingestion
# ---------------------------------------------------------------------------


@router.post("/content/ingest")
async def ingest_document(
    body: IngestRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Ingest a document into the RAG knowledge base."""
    from app.services.content_engine import ingest_document as do_ingest

    result = await do_ingest(
        db,
        str(user.id),
        body.text,
        source=body.source,
        title=body.title,
    )
    await db.commit()
    return result
