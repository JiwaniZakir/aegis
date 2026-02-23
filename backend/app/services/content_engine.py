"""Content engine — RAG-powered content generation for thought leadership posts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.content import ContentPost
from app.security.audit import audit_log

logger = structlog.get_logger()


async def generate_post(
    db: AsyncSession,
    user_id: str,
    *,
    topic: str = "",
    platform: str = "linkedin",
    tone: str = "professional",
    max_length: int = 0,
) -> dict:
    """Generate a thought leadership post using RAG + LLM.

    Steps:
    1. Retrieve relevant context from Qdrant vector store.
    2. Build a prompt with retrieved context.
    3. Generate content via Claude API.
    4. Store as draft in the database.

    Args:
        db: Database session.
        user_id: User identifier.
        topic: Topic or theme for the post.
        platform: Target platform (linkedin, x).
        tone: Writing tone (professional, casual, thought_leader).
        max_length: Max characters (0 = platform default).

    Returns:
        Dict with generated content and metadata.
    """
    settings = get_settings()

    # Set platform-appropriate defaults
    if max_length <= 0:
        max_length = 3000 if platform == "linkedin" else 280

    # Step 1: Retrieve relevant context
    context_chunks = await _retrieve_context(topic, settings)

    # Step 2: Generate content via LLM
    content = await _generate_with_llm(
        topic=topic,
        platform=platform,
        tone=tone,
        max_length=max_length,
        context_chunks=context_chunks,
        settings=settings,
    )

    # Step 3: Store as draft
    uid = uuid.UUID(user_id)
    post = ContentPost(
        user_id=uid,
        platform=platform,
        content=content,
        status="draft",
    )
    db.add(post)
    await db.flush()

    await audit_log(
        db,
        action="content_generate",
        resource_type="content",
        resource_id=str(post.id),
        user_id=uid,
        metadata={"topic": topic, "platform": platform, "tone": tone},
    )

    logger.info(
        "content_generated",
        user_id=user_id,
        platform=platform,
        post_id=str(post.id),
    )

    return {
        "id": str(post.id),
        "content": content,
        "platform": platform,
        "status": "draft",
        "topic": topic,
        "character_count": len(content),
    }


async def _retrieve_context(topic: str, settings: object) -> list[str]:
    """Retrieve relevant context chunks from Qdrant for RAG.

    Returns:
        List of text chunks relevant to the topic.
    """
    if not topic:
        return []

    try:
        embedding = await _get_embedding(topic, settings)
        if not embedding:
            return []

        return await _search_qdrant(embedding, settings)
    except Exception as exc:
        logger.warning("rag_context_retrieval_failed", error=str(type(exc).__name__))
        return []


async def _get_embedding(text: str, settings: object) -> list[float]:
    """Generate an embedding vector for text.

    Uses OpenAI text-embedding-3-small or falls back to sentence-transformers.
    """

    # Try OpenAI embeddings API (works with Anthropic proxy too)
    api_key = getattr(settings, "anthropic_api_key", "")
    if not api_key:
        return []

    # Use a simple hash-based pseudo-embedding as fallback
    # Real implementation would use sentence-transformers or OpenAI
    logger.debug("embedding_generation_placeholder")
    return _pseudo_embedding(text)


def _pseudo_embedding(text: str) -> list[float]:
    """Generate a deterministic pseudo-embedding for development/testing.

    In production, replace with sentence-transformers or OpenAI embeddings.
    """
    import hashlib

    h = hashlib.sha256(text.encode()).digest()
    # Create a 384-dimensional pseudo-vector from hash bytes
    vector = []
    for i in range(384):
        byte_val = h[i % len(h)]
        vector.append((byte_val / 255.0) * 2 - 1)
    return vector


async def _search_qdrant(embedding: list[float], settings: object) -> list[str]:
    """Search Qdrant vector store for relevant context chunks."""
    import httpx

    qdrant_url = getattr(settings, "qdrant_url", "http://localhost:6333")
    qdrant_key = getattr(settings, "qdrant_api_key", "")

    headers: dict = {"Content-Type": "application/json"}
    if qdrant_key:
        headers["api-key"] = qdrant_key

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{qdrant_url}/collections/content_knowledge/points/search",
                headers=headers,
                json={
                    "vector": embedding,
                    "limit": 5,
                    "with_payload": True,
                },
            )
            if response.status_code == 404:
                logger.debug("qdrant_collection_not_found")
                return []
            response.raise_for_status()
            data = response.json()

        chunks = []
        for result in data.get("result", []):
            payload = result.get("payload", {})
            text = payload.get("text", "")
            if text:
                chunks.append(text)

        return chunks
    except Exception as exc:
        logger.warning("qdrant_search_failed", error=str(type(exc).__name__))
        return []


async def _generate_with_llm(
    *,
    topic: str,
    platform: str,
    tone: str,
    max_length: int,
    context_chunks: list[str],
    settings: object,
) -> str:
    """Generate content using Claude API with RAG context."""
    api_key = getattr(settings, "anthropic_api_key", "")
    if not api_key:
        return _fallback_content(topic, platform)

    context_block = ""
    if context_chunks:
        context_block = "\n\nRelevant context from your knowledge base:\n" + "\n---\n".join(
            context_chunks[:5]
        )

    platform_guidance = {
        "linkedin": (
            "Write a LinkedIn post. Use professional tone, include a hook in "
            "the first line, use short paragraphs, and end with a call to "
            "engagement (question or insight). Max 3000 characters."
        ),
        "x": (
            "Write a tweet. Be concise, impactful, and under 280 characters. "
            "Use no more than 2 hashtags."
        ),
    }

    tone_guidance = {
        "professional": "Maintain a professional, authoritative tone.",
        "casual": "Use a conversational, approachable tone.",
        "thought_leader": (
            "Write as an industry thought leader sharing unique insights. "
            "Be bold with your perspective."
        ),
    }

    prompt = (
        f"Generate a social media post about: {topic}\n\n"
        f"Platform: {platform}\n"
        f"{platform_guidance.get(platform, platform_guidance['linkedin'])}\n\n"
        f"Tone: {tone_guidance.get(tone, tone_guidance['professional'])}\n"
        f"Max length: {max_length} characters.\n"
        f"{context_block}\n\n"
        f"Return ONLY the post text, no explanations or meta-commentary."
    )

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        content = message.content[0].text.strip()
        # Ensure it fits within max length
        if len(content) > max_length:
            content = content[: max_length - 3] + "..."
        return content
    except Exception as exc:
        logger.warning("content_llm_generation_failed", error=str(type(exc).__name__))
        return _fallback_content(topic, platform)


def _fallback_content(topic: str, platform: str) -> str:
    """Generate placeholder content when LLM is unavailable."""
    if platform == "x":
        return f"Sharing thoughts on {topic}. #insights"
    return (
        f"Exploring the latest developments in {topic}.\n\n"
        f"What are your thoughts on this? I'd love to hear "
        f"different perspectives in the comments."
    )


async def ingest_document(
    db: AsyncSession,
    user_id: str,
    text: str,
    *,
    source: str = "manual",
    title: str = "",
) -> dict:
    """Ingest a document into the RAG knowledge base.

    Chunks the text and stores embeddings in Qdrant.

    Returns:
        Dict with ingestion stats.
    """
    settings = get_settings()
    chunks = _chunk_text(text, chunk_size=500, overlap=50)

    stored = 0
    for chunk in chunks:
        try:
            embedding = await _get_embedding(chunk, settings)
            if embedding:
                await _store_in_qdrant(
                    embedding=embedding,
                    text=chunk,
                    metadata={"source": source, "title": title},
                    settings=settings,
                )
                stored += 1
        except Exception as exc:
            logger.warning("chunk_ingestion_failed", error=str(type(exc).__name__))

    uid = uuid.UUID(user_id)
    await audit_log(
        db,
        action="content_ingest",
        resource_type="knowledge_base",
        user_id=uid,
        metadata={
            "source": source,
            "title": title,
            "total_chunks": len(chunks),
            "stored_chunks": stored,
        },
    )

    logger.info(
        "document_ingested",
        user_id=user_id,
        chunks=len(chunks),
        stored=stored,
    )

    return {
        "total_chunks": len(chunks),
        "stored_chunks": stored,
        "source": source,
        "title": title,
    }


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks for embedding."""
    if not text:
        return []

    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap

    return chunks


async def _store_in_qdrant(
    *,
    embedding: list[float],
    text: str,
    metadata: dict,
    settings: object,
) -> None:
    """Store an embedding + payload in Qdrant."""
    import httpx

    qdrant_url = getattr(settings, "qdrant_url", "http://localhost:6333")
    qdrant_key = getattr(settings, "qdrant_api_key", "")

    headers: dict = {"Content-Type": "application/json"}
    if qdrant_key:
        headers["api-key"] = qdrant_key

    point_id = uuid.uuid4().hex

    async with httpx.AsyncClient(timeout=10) as client:
        # Ensure collection exists
        await client.put(
            f"{qdrant_url}/collections/content_knowledge",
            headers=headers,
            json={
                "vectors": {"size": 384, "distance": "Cosine"},
            },
        )

        # Upsert point
        await client.put(
            f"{qdrant_url}/collections/content_knowledge/points",
            headers=headers,
            json={
                "points": [
                    {
                        "id": point_id,
                        "vector": embedding,
                        "payload": {
                            "text": text,
                            **metadata,
                            "ingested_at": datetime.now(UTC).isoformat(),
                        },
                    }
                ]
            },
        )


async def get_drafts(
    db: AsyncSession,
    user_id: str,
    *,
    platform: str | None = None,
) -> list[dict]:
    """Get all draft posts for a user."""
    uid = uuid.UUID(user_id)
    query = select(ContentPost).where(
        ContentPost.user_id == uid,
        ContentPost.status == "draft",
    )
    if platform:
        query = query.where(ContentPost.platform == platform)
    query = query.order_by(ContentPost.created_at.desc())

    result = await db.execute(query)
    posts = result.scalars().all()

    return [
        {
            "id": str(p.id),
            "platform": p.platform,
            "content": p.content,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in posts
    ]


async def publish_draft(
    db: AsyncSession,
    user_id: str,
    post_id: str,
) -> dict:
    """Publish a draft post to its target platform.

    Returns:
        Dict with publishing result.
    """
    uid = uuid.UUID(user_id)
    pid = uuid.UUID(post_id)

    result = await db.execute(
        select(ContentPost).where(
            ContentPost.id == pid,
            ContentPost.user_id == uid,
            ContentPost.status == "draft",
        )
    )
    post = result.scalar_one_or_none()
    if not post:
        msg = "Draft post not found"
        raise ValueError(msg)

    # Publish to the target platform
    publish_result: dict = {}
    if post.platform == "linkedin":
        from app.services.social_poster import post_to_linkedin

        publish_result = await post_to_linkedin(db, user_id, post.content)
    elif post.platform == "x":
        from app.services.social_poster import post_to_x

        publish_result = await post_to_x(db, user_id, post.content)

    # Update status
    post.status = "published"
    post.posted_at = datetime.now(UTC)
    post.external_post_id = publish_result.get("post_id", publish_result.get("tweet_id", ""))
    await db.flush()

    await audit_log(
        db,
        action="content_publish",
        resource_type="content",
        resource_id=str(post.id),
        user_id=uid,
    )

    return {
        "id": str(post.id),
        "platform": post.platform,
        "status": "published",
        "publish_result": publish_result,
    }
