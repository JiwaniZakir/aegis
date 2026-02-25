"""Contact graph endpoints."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User

logger = structlog.get_logger()

router = APIRouter(tags=["contacts"])


# ---------------------------------------------------------------------------
# Pydantic request schemas
# ---------------------------------------------------------------------------


class ContactCreateRequest(BaseModel):
    name: str
    source: str
    email: str | None = None
    phone: str | None = None
    category: str | None = None
    company: str | None = None
    industry: str | None = None


class ContactEdgeRequest(BaseModel):
    contact_a_id: str
    contact_b_id: str
    relationship_type: str
    weight: float = 1.0


class ContactMergeRequest(BaseModel):
    contact_ids: list[str]


# ---------------------------------------------------------------------------
# Contact graph endpoints
# ---------------------------------------------------------------------------


@router.post("/contacts")
async def create_contact(
    body: ContactCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add a new contact to the relationship graph."""
    from app.services.contact_graph import add_contact

    contact = await add_contact(
        db,
        str(user.id),
        name=body.name,
        source=body.source,
        email=body.email,
        phone=body.phone,
        category=body.category,
        company=body.company,
        industry=body.industry,
    )
    await db.commit()
    return contact


@router.post("/contacts/edge")
async def create_contact_edge(
    body: ContactEdgeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a relationship edge between two contacts."""
    from app.services.contact_graph import add_edge

    edge = await add_edge(
        db,
        str(user.id),
        contact_a_id=body.contact_a_id,
        contact_b_id=body.contact_b_id,
        relationship_type=body.relationship_type,
        weight=body.weight,
    )
    await db.commit()
    return edge


@router.post("/contacts/merge")
async def merge_contacts(
    body: ContactMergeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Merge duplicate contacts into one."""
    from app.services.contact_graph import merge_contacts as do_merge

    result = await do_merge(db, str(user.id), body.contact_ids)
    await db.commit()
    return result


@router.get("/contacts/graph")
async def get_contact_graph(
    center_id: str = Query(..., description="Contact ID to center the graph on"),
    depth: int = Query(2, ge=1, le=5),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get network graph around a contact for visualization."""
    from app.services.contact_graph import get_network_graph

    return await get_network_graph(db, str(user.id), center_id, depth=depth)


@router.get("/contacts/shortest-path")
async def get_shortest_path(
    from_id: str = Query(...),
    to_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Find shortest path between two contacts for warm intros."""
    from app.services.contact_graph import shortest_path

    try:
        path = await shortest_path(db, str(user.id), from_id, to_id)
        return {"path": path, "hops": len(path) - 1}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/contacts/suggest-outreach")
async def get_outreach_suggestions(
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Suggest contacts to reconnect with based on relationship decay."""
    from app.services.contact_graph import suggest_outreach

    return await suggest_outreach(db, str(user.id), limit=limit)
