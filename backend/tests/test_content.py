"""Tests for content engine, RAG, and auto-posting."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Text chunking tests
# ---------------------------------------------------------------------------


def test_chunk_text_basic():
    """Basic text chunking produces correct number of chunks."""
    from app.services.content_engine import _chunk_text

    text = " ".join(f"word{i}" for i in range(100))
    chunks = _chunk_text(text, chunk_size=50, overlap=10)
    assert len(chunks) == 3  # 0-49, 40-89, 80-99


def test_chunk_text_empty():
    """Empty text returns empty list."""
    from app.services.content_engine import _chunk_text

    assert _chunk_text("") == []


def test_chunk_text_short():
    """Short text returns single chunk."""
    from app.services.content_engine import _chunk_text

    chunks = _chunk_text("hello world", chunk_size=500)
    assert len(chunks) == 1
    assert chunks[0] == "hello world"


def test_chunk_text_overlap():
    """Overlapping chunks share words at boundaries."""
    from app.services.content_engine import _chunk_text

    words = [f"w{i}" for i in range(20)]
    text = " ".join(words)
    chunks = _chunk_text(text, chunk_size=10, overlap=3)
    # First chunk: w0-w9, second: w7-w16, third: w14-w19
    assert "w7" in chunks[0]
    assert "w7" in chunks[1]


# ---------------------------------------------------------------------------
# Pseudo embedding tests
# ---------------------------------------------------------------------------


def test_pseudo_embedding_deterministic():
    """Pseudo embedding is deterministic for same input."""
    from app.services.content_engine import _pseudo_embedding

    emb1 = _pseudo_embedding("test text")
    emb2 = _pseudo_embedding("test text")
    assert emb1 == emb2


def test_pseudo_embedding_dimension():
    """Pseudo embedding has expected dimensions."""
    from app.services.content_engine import _pseudo_embedding

    emb = _pseudo_embedding("test")
    assert len(emb) == 384
    assert all(isinstance(v, float) for v in emb)
    assert all(-1 <= v <= 1 for v in emb)


def test_pseudo_embedding_different_inputs():
    """Different inputs produce different embeddings."""
    from app.services.content_engine import _pseudo_embedding

    emb1 = _pseudo_embedding("hello")
    emb2 = _pseudo_embedding("world")
    assert emb1 != emb2


# ---------------------------------------------------------------------------
# Fallback content tests
# ---------------------------------------------------------------------------


def test_fallback_content_linkedin():
    """LinkedIn fallback content contains topic."""
    from app.services.content_engine import _fallback_content

    result = _fallback_content("machine learning", "linkedin")
    assert "machine learning" in result
    assert len(result) > 20


def test_fallback_content_x():
    """X fallback content is short and contains topic."""
    from app.services.content_engine import _fallback_content

    result = _fallback_content("AI", "x")
    assert "AI" in result
    assert len(result) <= 280


# ---------------------------------------------------------------------------
# Content engine imports
# ---------------------------------------------------------------------------


def test_content_engine_imports():
    """Content engine service functions are importable."""
    from app.services.content_engine import (
        generate_post,
        get_drafts,
        ingest_document,
        publish_draft,
    )

    assert callable(generate_post)
    assert callable(get_drafts)
    assert callable(ingest_document)
    assert callable(publish_draft)


# ---------------------------------------------------------------------------
# API router registration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_content_generate_endpoint_registered(client):
    """Content generate endpoint is registered."""
    response = await client.post(
        "/api/v1/content/generate",
        json={"topic": "AI", "platform": "linkedin"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_content_publish_endpoint_registered(client):
    """Content publish endpoint is registered."""
    response = await client.post(
        "/api/v1/content/publish",
        json={"post_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_content_drafts_endpoint_registered(client):
    """Content drafts endpoint is registered."""
    response = await client.get("/api/v1/content/drafts")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_content_ingest_endpoint_registered(client):
    """Content ingest endpoint is registered."""
    response = await client.post(
        "/api/v1/content/ingest",
        json={"text": "test content here for ingestion", "source": "test"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# LinkedInClient import and structure tests
# ---------------------------------------------------------------------------


def test_linkedin_client_import():
    """LinkedInClient can be imported from the integrations module."""
    from app.integrations.linkedin_client import LinkedInClient, LinkedInClientError

    assert LinkedInClient is not None
    assert LinkedInClientError is not None


def test_linkedin_client_is_base_integration():
    """LinkedInClient inherits from BaseIntegration."""
    from app.integrations.base import BaseIntegration
    from app.integrations.linkedin_client import LinkedInClient

    assert issubclass(LinkedInClient, BaseIntegration)


def test_linkedin_client_has_required_methods():
    """LinkedInClient has sync, health_check, and posting methods."""
    from app.integrations.linkedin_client import LinkedInClient

    assert hasattr(LinkedInClient, "sync")
    assert hasattr(LinkedInClient, "health_check")
    assert hasattr(LinkedInClient, "create_post")
    assert hasattr(LinkedInClient, "get_profile")
    assert hasattr(LinkedInClient, "get_feed")
    assert hasattr(LinkedInClient, "store_post")


# ---------------------------------------------------------------------------
# XClient import and structure tests
# ---------------------------------------------------------------------------


def test_x_client_import():
    """XClient can be imported from the integrations module."""
    from app.integrations.x_client import XClient, XClientError

    assert XClient is not None
    assert XClientError is not None


def test_x_client_is_base_integration():
    """XClient inherits from BaseIntegration."""
    from app.integrations.base import BaseIntegration
    from app.integrations.x_client import XClient

    assert issubclass(XClient, BaseIntegration)


def test_x_client_has_required_methods():
    """XClient has sync, health_check, and tweeting methods."""
    from app.integrations.x_client import XClient

    assert hasattr(XClient, "sync")
    assert hasattr(XClient, "health_check")
    assert hasattr(XClient, "create_tweet")
    assert hasattr(XClient, "get_user_tweets")
    assert hasattr(XClient, "get_me")
    assert hasattr(XClient, "search_tweets")
    assert hasattr(XClient, "store_tweet")


# ---------------------------------------------------------------------------
# Content engine service tests (mocked DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_post_uses_fallback_without_api_key():
    """generate_post falls back to placeholder content when no API key."""
    import uuid
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.content_engine import generate_post

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    # Mock db.flush() and db.add()
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    # Mock the ContentPost to have an id after flush
    with (
        patch("app.services.content_engine.audit_log", new_callable=AsyncMock),
        patch(
            "app.services.content_engine.ContentPost",
            return_value=MagicMock(id=uuid.uuid4()),
        ),
        patch(
            "app.services.content_engine._retrieve_context",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result = await generate_post(mock_db, user_id, topic="AI trends", platform="linkedin")

    assert "content" in result
    assert "platform" in result
    assert result["platform"] == "linkedin"
    assert result["status"] == "draft"
    assert "AI trends" in result["content"]


@pytest.mark.asyncio
async def test_generate_post_x_platform():
    """generate_post uses X-appropriate defaults for short posts."""
    import uuid
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.content_engine import generate_post

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    with (
        patch("app.services.content_engine.audit_log", new_callable=AsyncMock),
        patch(
            "app.services.content_engine.ContentPost",
            return_value=MagicMock(id=uuid.uuid4()),
        ),
        patch(
            "app.services.content_engine._retrieve_context",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result = await generate_post(mock_db, user_id, topic="AI", platform="x")

    assert result["platform"] == "x"
    assert len(result["content"]) <= 280


@pytest.mark.asyncio
async def test_get_drafts_empty():
    """get_drafts returns empty list when no drafts exist."""
    import uuid
    from unittest.mock import AsyncMock, MagicMock

    from app.services.content_engine import get_drafts

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    result = await get_drafts(mock_db, user_id)
    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_ingest_document_chunks_text():
    """ingest_document chunks text and attempts to store embeddings."""
    import uuid
    from unittest.mock import AsyncMock, patch

    from app.services.content_engine import ingest_document

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    # Generate enough text to produce multiple chunks
    text = " ".join(f"word{i}" for i in range(600))

    with (
        patch("app.services.content_engine.audit_log", new_callable=AsyncMock),
        patch(
            "app.services.content_engine._store_in_qdrant",
            new_callable=AsyncMock,
        ),
    ):
        result = await ingest_document(mock_db, user_id, text, source="test")

    assert "total_chunks" in result
    assert "stored_chunks" in result
    assert result["total_chunks"] > 1
    assert result["source"] == "test"


@pytest.mark.asyncio
async def test_ingest_document_empty_text():
    """ingest_document handles empty text gracefully."""
    import uuid
    from unittest.mock import AsyncMock, patch

    from app.services.content_engine import ingest_document

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    with patch("app.services.content_engine.audit_log", new_callable=AsyncMock):
        result = await ingest_document(mock_db, user_id, "", source="test")

    assert result["total_chunks"] == 0
    assert result["stored_chunks"] == 0
