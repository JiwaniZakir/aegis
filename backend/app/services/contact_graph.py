"""Contact graph service — relationship intelligence, network analysis, and outreach."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact, ContactEdge
from app.security.audit import audit_log

try:
    import networkx as nx
except ImportError as _nx_err:
    msg = "networkx is required for contact_graph. Install it with: uv add networkx"
    raise ImportError(msg) from _nx_err

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


async def _build_networkx_graph(
    db: AsyncSession,
    user_id: str,
) -> tuple[nx.Graph, dict[uuid.UUID, Contact]]:
    """Load all contacts and edges for a user into a NetworkX graph.

    Returns:
        A tuple of (nx.Graph, lookup dict mapping contact id -> Contact).
    """
    uid = uuid.UUID(user_id)

    contacts_result = await db.execute(select(Contact).where(Contact.user_id == uid))
    contacts = contacts_result.scalars().all()

    contact_lookup: dict[uuid.UUID, Contact] = {c.id: c for c in contacts}
    contact_ids = set(contact_lookup.keys())

    graph = nx.Graph()
    for contact in contacts:
        graph.add_node(
            contact.id,
            name=contact.name,
            email=contact.email,
            source=contact.source,
            category=contact.category,
            company=contact.company,
            relationship_strength=contact.relationship_strength,
        )

    if contact_ids:
        edges_result = await db.execute(
            select(ContactEdge).where(
                and_(
                    ContactEdge.contact_a_id.in_(contact_ids),
                    ContactEdge.contact_b_id.in_(contact_ids),
                )
            )
        )
        edges = edges_result.scalars().all()

        for edge in edges:
            graph.add_edge(
                edge.contact_a_id,
                edge.contact_b_id,
                relationship_type=edge.relationship_type,
                weight=edge.weight,
                edge_id=edge.id,
            )

    return graph, contact_lookup


# ---------------------------------------------------------------------------
# Contact CRUD
# ---------------------------------------------------------------------------


def _contact_to_dict(contact: Contact) -> dict:
    """Serialize a Contact model to a plain dict (no encrypted fields)."""
    return {
        "id": str(contact.id),
        "name": contact.name,
        "email": contact.email,
        "phone": contact.phone,
        "source": contact.source,
        "category": contact.category,
        "company": contact.company,
        "industry": contact.industry,
        "relationship_strength": contact.relationship_strength,
        "last_interaction": (
            contact.last_interaction.isoformat() if contact.last_interaction else None
        ),
        "notes": contact.notes,
    }


async def add_contact(
    db: AsyncSession,
    user_id: str,
    name: str,
    source: str,
    **metadata: str | float | None,
) -> dict:
    """Add a new contact or merge into an existing one matched by email.

    If a contact with the same email already exists for this user, the
    existing record is updated with any non-null metadata fields instead
    of creating a duplicate.

    Returns:
        dict representation of the created/updated contact.
    """
    uid = uuid.UUID(user_id)
    email = metadata.get("email")

    # Attempt to merge on email if provided
    existing: Contact | None = None
    if email:
        result = await db.execute(
            select(Contact).where(
                and_(
                    Contact.user_id == uid,
                    Contact.email == email,
                )
            )
        )
        existing = result.scalar_one_or_none()

    if existing is not None:
        # Merge: update only fields that are currently empty
        for field in (
            "phone",
            "category",
            "company",
            "industry",
            "notes",
        ):
            incoming = metadata.get(field)
            if incoming and not getattr(existing, field):
                setattr(existing, field, incoming)

        # Always update last_interaction if provided
        if metadata.get("last_interaction"):
            existing.last_interaction = metadata["last_interaction"]  # type: ignore[assignment]

        # Prefer higher relationship strength
        incoming_strength = metadata.get("relationship_strength")
        if (
            incoming_strength is not None
            and float(incoming_strength) > existing.relationship_strength
        ):
            existing.relationship_strength = float(incoming_strength)

        await db.flush()
        contact = existing
        logger.info(
            "contact_merged",
            user_id=user_id,
            contact_id=str(contact.id),
            source=source,
        )
    else:
        allowed_fields = {
            "email",
            "phone",
            "category",
            "company",
            "industry",
            "relationship_strength",
            "last_interaction",
            "notes",
        }
        filtered = {k: v for k, v in metadata.items() if k in allowed_fields}
        contact = Contact(user_id=uid, name=name, source=source, **filtered)
        db.add(contact)
        await db.flush()
        logger.info(
            "contact_created",
            user_id=user_id,
            contact_id=str(contact.id),
            source=source,
        )

    await audit_log(
        db,
        action="add_contact",
        resource_type="contact",
        resource_id=str(contact.id),
        user_id=uid,
        metadata={"source": source},
    )

    return _contact_to_dict(contact)


async def add_edge(
    db: AsyncSession,
    user_id: str,
    contact_a_id: str,
    contact_b_id: str,
    relationship_type: str,
    weight: float = 1.0,
) -> dict:
    """Create a connection edge between two contacts.

    If the edge already exists with the same relationship type, its weight
    is updated instead.

    Returns:
        dict with edge details.
    """
    uid = uuid.UUID(user_id)
    a_id = uuid.UUID(contact_a_id)
    b_id = uuid.UUID(contact_b_id)

    # Validate both contacts belong to this user
    for cid in (a_id, b_id):
        result = await db.execute(
            select(Contact.id).where(and_(Contact.id == cid, Contact.user_id == uid))
        )
        if result.scalar_one_or_none() is None:
            msg = f"Contact {cid} not found for user {user_id}"
            raise ValueError(msg)

    # Check for existing edge (either direction)
    existing_result = await db.execute(
        select(ContactEdge).where(
            and_(
                ContactEdge.relationship_type == relationship_type,
                ((ContactEdge.contact_a_id == a_id) & (ContactEdge.contact_b_id == b_id))
                | ((ContactEdge.contact_a_id == b_id) & (ContactEdge.contact_b_id == a_id)),
            )
        )
    )
    existing_edge = existing_result.scalar_one_or_none()

    if existing_edge is not None:
        existing_edge.weight = weight
        await db.flush()
        edge = existing_edge
        logger.info(
            "edge_updated",
            edge_id=str(edge.id),
            weight=weight,
        )
    else:
        edge = ContactEdge(
            contact_a_id=a_id,
            contact_b_id=b_id,
            relationship_type=relationship_type,
            weight=weight,
        )
        db.add(edge)
        await db.flush()
        logger.info(
            "edge_created",
            edge_id=str(edge.id),
            contact_a=contact_a_id,
            contact_b=contact_b_id,
        )

    await audit_log(
        db,
        action="add_edge",
        resource_type="contact_edge",
        resource_id=str(edge.id),
        user_id=uid,
        metadata={
            "contact_a_id": contact_a_id,
            "contact_b_id": contact_b_id,
            "relationship_type": relationship_type,
        },
    )

    return {
        "id": str(edge.id),
        "contact_a_id": str(edge.contact_a_id),
        "contact_b_id": str(edge.contact_b_id),
        "relationship_type": edge.relationship_type,
        "weight": edge.weight,
    }


# ---------------------------------------------------------------------------
# Merge / deduplication
# ---------------------------------------------------------------------------


async def merge_contacts(
    db: AsyncSession,
    user_id: str,
    contact_ids: list[str],
) -> dict:
    """Merge multiple contacts into one, keeping the richest data.

    The contact with the most populated fields is chosen as the primary.
    All edges pointing to the merged contacts are re-pointed to the primary.
    Duplicate contacts are deleted.

    Returns:
        dict of the merged (surviving) contact.
    """
    if len(contact_ids) < 2:
        msg = "At least two contact IDs are required for merge"
        raise ValueError(msg)

    uid = uuid.UUID(user_id)
    parsed_ids = [uuid.UUID(cid) for cid in contact_ids]

    result = await db.execute(
        select(Contact).where(
            and_(
                Contact.id.in_(parsed_ids),
                Contact.user_id == uid,
            )
        )
    )
    contacts = list(result.scalars().all())

    if len(contacts) != len(parsed_ids):
        found = {c.id for c in contacts}
        missing = [cid for cid in parsed_ids if cid not in found]
        msg = f"Contacts not found: {missing}"
        raise ValueError(msg)

    # Score each contact by number of non-null fields
    mergeable_fields = (
        "email",
        "phone",
        "category",
        "company",
        "industry",
        "last_interaction",
        "notes",
    )

    def _richness(c: Contact) -> int:
        return sum(1 for f in mergeable_fields if getattr(c, f) is not None)

    contacts.sort(key=_richness, reverse=True)
    primary = contacts[0]
    duplicates = contacts[1:]

    # Enrich primary with data from duplicates
    for field in mergeable_fields:
        if getattr(primary, field) is None:
            for dup in duplicates:
                val = getattr(dup, field)
                if val is not None:
                    setattr(primary, field, val)
                    break

    # Keep the highest relationship strength
    max_strength = max(c.relationship_strength for c in contacts)
    primary.relationship_strength = max_strength

    # Consolidate sources
    sources = {c.source for c in contacts}
    primary.source = ",".join(sorted(sources))

    # Re-point edges from duplicates to primary
    dup_ids = {d.id for d in duplicates}
    for dup_id in dup_ids:
        # Edges where duplicate is contact_a
        edges_a = await db.execute(select(ContactEdge).where(ContactEdge.contact_a_id == dup_id))
        for edge in edges_a.scalars().all():
            if edge.contact_b_id in dup_ids or edge.contact_b_id == primary.id:
                await db.delete(edge)
            else:
                edge.contact_a_id = primary.id

        # Edges where duplicate is contact_b
        edges_b = await db.execute(select(ContactEdge).where(ContactEdge.contact_b_id == dup_id))
        for edge in edges_b.scalars().all():
            if edge.contact_a_id in dup_ids or edge.contact_a_id == primary.id:
                await db.delete(edge)
            else:
                edge.contact_b_id = primary.id

    # Delete duplicates
    for dup in duplicates:
        await db.delete(dup)

    await db.flush()

    await audit_log(
        db,
        action="merge_contacts",
        resource_type="contact",
        resource_id=str(primary.id),
        user_id=uid,
        metadata={
            "merged_ids": [str(d.id) for d in duplicates],
            "surviving_id": str(primary.id),
        },
    )

    logger.info(
        "contacts_merged",
        user_id=user_id,
        primary_id=str(primary.id),
        merged_count=len(duplicates),
    )
    return _contact_to_dict(primary)


# ---------------------------------------------------------------------------
# Graph queries
# ---------------------------------------------------------------------------


async def get_network_graph(
    db: AsyncSession,
    user_id: str,
    center_contact_id: str,
    depth: int = 2,
) -> dict:
    """Return the subgraph within *depth* hops of *center_contact_id*.

    Returns:
        dict with ``nodes`` (list of contact dicts) and ``edges`` (list of
        edge dicts) suitable for front-end graph rendering.
    """
    uid = uuid.UUID(user_id)
    center_id = uuid.UUID(center_contact_id)

    graph, contact_lookup = await _build_networkx_graph(db, user_id)

    if center_id not in graph:
        msg = f"Contact {center_contact_id} not found in graph"
        raise ValueError(msg)

    # BFS neighbourhood up to *depth* hops
    neighbourhood: set[uuid.UUID] = set()
    frontier: set[uuid.UUID] = {center_id}
    for _ in range(depth):
        next_frontier: set[uuid.UUID] = set()
        for node in frontier:
            for neighbour in graph.neighbors(node):
                if neighbour not in neighbourhood and neighbour not in frontier:
                    next_frontier.add(neighbour)
        neighbourhood.update(frontier)
        frontier = next_frontier
    neighbourhood.update(frontier)

    subgraph = graph.subgraph(neighbourhood)

    nodes = []
    for nid in subgraph.nodes:
        contact = contact_lookup.get(nid)
        if contact is not None:
            node_dict = _contact_to_dict(contact)
            node_dict["is_center"] = nid == center_id
            nodes.append(node_dict)

    edges = []
    for a_id, b_id, data in subgraph.edges(data=True):
        edges.append(
            {
                "source": str(a_id),
                "target": str(b_id),
                "relationship_type": data.get("relationship_type", "unknown"),
                "weight": data.get("weight", 1.0),
            }
        )

    await audit_log(
        db,
        action="get_network_graph",
        resource_type="contact",
        resource_id=center_contact_id,
        user_id=uid,
        metadata={"depth": depth, "node_count": len(nodes)},
    )

    logger.info(
        "network_graph_retrieved",
        user_id=user_id,
        center=center_contact_id,
        nodes=len(nodes),
        edges=len(edges),
    )
    return {"nodes": nodes, "edges": edges}


async def shortest_path(
    db: AsyncSession,
    user_id: str,
    from_contact_id: str,
    to_contact_id: str,
) -> list[dict]:
    """Compute the shortest path between two contacts for warm-intro chains.

    Uses inverse edge weight so stronger relationships are preferred.

    Returns:
        Ordered list of contact dicts along the path (inclusive of endpoints).
        Empty list if no path exists.
    """
    uid = uuid.UUID(user_id)
    from_id = uuid.UUID(from_contact_id)
    to_id = uuid.UUID(to_contact_id)

    graph, contact_lookup = await _build_networkx_graph(db, user_id)

    if from_id not in graph or to_id not in graph:
        return []

    try:
        path_ids: list[uuid.UUID] = nx.shortest_path(
            graph,
            source=from_id,
            target=to_id,
            weight="weight",
        )
    except nx.NetworkXNoPath:
        return []

    path_contacts = []
    for nid in path_ids:
        contact = contact_lookup.get(nid)
        if contact is not None:
            path_contacts.append(_contact_to_dict(contact))

    await audit_log(
        db,
        action="shortest_path",
        resource_type="contact",
        user_id=uid,
        metadata={
            "from": from_contact_id,
            "to": to_contact_id,
            "hops": len(path_contacts) - 1 if path_contacts else None,
        },
    )

    logger.info(
        "shortest_path_computed",
        user_id=user_id,
        hops=len(path_contacts) - 1 if path_contacts else 0,
    )
    return path_contacts


async def degree_of_separation(
    db: AsyncSession,
    user_id: str,
    from_contact_id: str,
    to_contact_id: str,
) -> int | None:
    """Return the number of hops between two contacts.

    Returns:
        Integer hop count, or None if no path exists.
    """
    from_id = uuid.UUID(from_contact_id)
    to_id = uuid.UUID(to_contact_id)

    graph, _ = await _build_networkx_graph(db, user_id)

    if from_id not in graph or to_id not in graph:
        return None

    try:
        length: int = nx.shortest_path_length(graph, source=from_id, target=to_id)
    except nx.NetworkXNoPath:
        return None

    logger.info(
        "degree_of_separation_computed",
        user_id=user_id,
        from_contact=from_contact_id,
        to_contact=to_contact_id,
        hops=length,
    )
    return length


# ---------------------------------------------------------------------------
# Outreach suggestions
# ---------------------------------------------------------------------------


async def suggest_outreach(
    db: AsyncSession,
    user_id: str,
    limit: int = 10,
) -> list[dict]:
    """Identify contacts to reconnect with based on staleness and value.

    Scoring formula:
        score = relationship_strength * days_since_last_interaction

    Higher scores indicate high-value contacts that have gone cold.
    Contacts with no recorded last_interaction are treated as maximally stale.

    Returns:
        List of contact dicts ordered by reconnection priority (descending).
    """
    uid = uuid.UUID(user_id)
    now = datetime.now(UTC)

    result = await db.execute(
        select(Contact).where(
            and_(
                Contact.user_id == uid,
                Contact.relationship_strength > 0,
            )
        )
    )
    contacts = result.scalars().all()

    scored: list[tuple[float, Contact]] = []
    for contact in contacts:
        if contact.last_interaction is not None:
            delta = now - contact.last_interaction
            days_stale = max(delta.total_seconds() / 86400, 0)
        else:
            # No interaction recorded — treat as very stale
            days_stale = 365.0

        score = contact.relationship_strength * days_stale
        scored.append((score, contact))

    scored.sort(key=lambda t: t[0], reverse=True)

    suggestions = []
    for score, contact in scored[:limit]:
        entry = _contact_to_dict(contact)
        entry["outreach_score"] = round(score, 2)
        days_ago = None
        if contact.last_interaction is not None:
            days_ago = (now - contact.last_interaction).days
        entry["days_since_interaction"] = days_ago
        suggestions.append(entry)

    await audit_log(
        db,
        action="suggest_outreach",
        resource_type="contact",
        user_id=uid,
        metadata={"limit": limit, "returned": len(suggestions)},
    )

    logger.info(
        "outreach_suggestions_generated",
        user_id=user_id,
        count=len(suggestions),
    )
    return suggestions


# ---------------------------------------------------------------------------
# Meeting enrichment
# ---------------------------------------------------------------------------


async def enrich_from_meeting(
    db: AsyncSession,
    user_id: str,
    meeting_data: dict,
) -> dict:
    """Extract attendees from meeting data, create/update contacts and edges.

    Expected *meeting_data* shape::

        {
            "title": "Weekly standup",
            "attendees": [
                {"name": "Alice", "email": "alice@corp.com"},
                {"name": "Bob", "email": "bob@corp.com"},
            ],
            "date": "2026-02-20T10:00:00Z",  # optional ISO string
        }

    All attendees are linked to each other with a ``meeting`` edge.

    Returns:
        dict with ``contacts_created``, ``contacts_updated``, and
        ``edges_created`` counts.
    """
    attendees = meeting_data.get("attendees", [])
    if not attendees:
        return {"contacts_created": 0, "contacts_updated": 0, "edges_created": 0}

    meeting_date: datetime | None = None
    raw_date = meeting_data.get("date")
    if isinstance(raw_date, str):
        try:
            meeting_date = datetime.fromisoformat(raw_date)
        except ValueError:
            logger.warning("meeting_date_parse_failed", raw=raw_date)

    created = 0
    updated = 0
    contact_ids: list[str] = []

    uid = uuid.UUID(user_id)
    for attendee in attendees:
        name = attendee.get("name", "Unknown")
        email = attendee.get("email")

        # Try to find existing contact by email
        existing: Contact | None = None
        if email:
            res = await db.execute(
                select(Contact).where(and_(Contact.user_id == uid, Contact.email == email))
            )
            existing = res.scalar_one_or_none()

        if existing is not None:
            if meeting_date is not None and (
                existing.last_interaction is None or meeting_date > existing.last_interaction
            ):
                existing.last_interaction = meeting_date
            updated += 1
            contact_ids.append(str(existing.id))
            await db.flush()
        else:
            meta: dict[str, str | datetime | None] = {}
            if email:
                meta["email"] = email
            if meeting_date is not None:
                meta["last_interaction"] = meeting_date
            contact_dict = await add_contact(db, user_id, name, source="meeting", **meta)
            created += 1
            contact_ids.append(contact_dict["id"])

    # Create meeting edges between all pairs of attendees
    edges_created = 0
    for i in range(len(contact_ids)):
        for j in range(i + 1, len(contact_ids)):
            try:
                await add_edge(
                    db,
                    user_id,
                    contact_ids[i],
                    contact_ids[j],
                    relationship_type="meeting",
                    weight=1.0,
                )
                edges_created += 1
            except ValueError:
                logger.warning(
                    "meeting_edge_creation_failed",
                    a=contact_ids[i],
                    b=contact_ids[j],
                )

    await audit_log(
        db,
        action="enrich_from_meeting",
        resource_type="contact",
        user_id=uid,
        metadata={
            "meeting_title": meeting_data.get("title"),
            "attendee_count": len(attendees),
            "contacts_created": created,
            "contacts_updated": updated,
            "edges_created": edges_created,
        },
    )

    logger.info(
        "meeting_enrichment_complete",
        user_id=user_id,
        created=created,
        updated=updated,
        edges=edges_created,
    )
    return {
        "contacts_created": created,
        "contacts_updated": updated,
        "edges_created": edges_created,
    }
