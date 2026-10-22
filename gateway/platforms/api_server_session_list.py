"""``GET /api/sessions`` page query, lifted from ``platforms/api_server.py``.

Keeps the api_server facade under its frozen line cap (root AGENTS.md god-file
guidance: move code into a topical sibling).
"""

import asyncio

ARCHIVED_VIEWS = ("exclude", "only", "include")


def archived_view_filters(value):
    """``list_sessions_rich`` kwargs for ``archived=exclude|only|include`` (the dashboard's
    vocabulary; absent means ``exclude``), or ``None`` for any other value.

    PATCH can archive a row, so the list must be able to reach it again (#139805). ``only`` is
    the SessionDB recovery view, which also returns archived rows that are hidden (#90946). It
    skips the pin back-fill, which would leak live pinned rows into the archived view."""
    view = value or "exclude"
    if view not in ARCHIVED_VIEWS:
        return None
    return {"include_archived": view == "include", "archived_only": view == "only",
            "include_pinned": view != "only"}


async def list_session_rows(db, *, title_filter, archive, **filters):
    """One page of ``list_sessions_rich`` off the event loop. ``include_pinned`` back-fills pins
    past the recency window; search_query pushes the title needle into SQL (substring) so a
    hidden/old row is found, exact match here."""
    rows = await asyncio.to_thread(
        db.list_sessions_rich, order_by_last_active=True, search_query=title_filter, **archive, **filters)
    if title_filter:
        rows = [s for s in rows if (s.get("title") or "").strip() == title_filter]
    return rows


def windowed_count(sessions, archive):
    """Rows that count toward ``has_more``: back-filled pins arrive PAST the limit, so counting
    them would report a page that doesn't exist. Without the back-fill every row counts."""
    return sum(1 for s in sessions if not (archive["include_pinned"] and s.get("pinned")))
