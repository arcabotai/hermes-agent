"""GET /api/sessions honours the ``archived`` filter (#139805).

PATCH /api/sessions/{id} can set ``archived: true``; before this filter the list endpoint
always returned the non-archived view, so an archived session could not be listed again.
"""

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from gateway.config import PlatformConfig
from gateway.platforms.api_server import APIServerAdapter
from hermes_state import SessionDB


@pytest.fixture
def session_db(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def app(session_db):
    adapter = APIServerAdapter(PlatformConfig(enabled=True))
    adapter._session_db = session_db
    app = web.Application()
    app.router.add_get("/api/sessions", adapter._handle_list_sessions)
    app.router.add_patch("/api/sessions/{session_id}", adapter._handle_patch_session)
    return app


async def _ids(cli, query=""):
    resp = await cli.get("/api/sessions" + query)
    assert resp.status == 200, await resp.text()
    return {row["id"] for row in (await resp.json())["data"]}


@pytest.mark.asyncio
async def test_archived_session_patched_over_the_api_is_listable_again(app, session_db):
    session_db.create_session("live", "api_server")
    session_db.create_session("old", "api_server")
    async with TestClient(TestServer(app)) as cli:
        resp = await cli.patch("/api/sessions/old", json={"archived": True})
        assert resp.status == 200, await resp.text()

        assert await _ids(cli) == {"live"}
        assert await _ids(cli, "?archived=exclude") == {"live"}
        assert await _ids(cli, "?archived=only") == {"old"}
        assert await _ids(cli, "?archived=include") == {"live", "old"}

        resp = await cli.get("/api/sessions?archived=only")
        rows = (await resp.json())["data"]
    assert [row["archived"] for row in rows] == [True]


@pytest.mark.asyncio
async def test_archived_only_view_does_not_backfill_live_pins(app, session_db):
    session_db.create_session("pinned-live", "api_server")
    assert session_db.set_session_pinned("pinned-live", True)
    session_db.create_session("pinned-old", "api_server")
    assert session_db.set_session_pinned("pinned-old", True)
    assert session_db.set_session_archived("pinned-old", True)
    async with TestClient(TestServer(app)) as cli:
        assert await _ids(cli, "?archived=only") == {"pinned-old"}
        # The default list keeps its pin back-fill: a pinned archived row stays reachable.
        assert await _ids(cli) == {"pinned-live", "pinned-old"}


@pytest.mark.asyncio
async def test_archived_only_page_reports_has_more_for_pinned_rows(app, session_db):
    for sid in ("a", "b"):
        session_db.create_session(sid, "api_server")
        assert session_db.set_session_pinned(sid, True)
        assert session_db.set_session_archived(sid, True)
    async with TestClient(TestServer(app)) as cli:
        resp = await cli.get("/api/sessions?archived=only&limit=1")
        payload = await resp.json()
    assert len(payload["data"]) == 1
    assert payload["has_more"] is True


@pytest.mark.asyncio
async def test_unknown_archived_value_is_refused(app, session_db):
    session_db.create_session("live", "api_server")
    async with TestClient(TestServer(app)) as cli:
        resp = await cli.get("/api/sessions?archived=yes")
        assert resp.status == 400
        assert (await resp.json())["error"]["code"] == "invalid_archived"
