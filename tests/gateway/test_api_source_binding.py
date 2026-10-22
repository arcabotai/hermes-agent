"""API source restoration cannot mint a parallel native conversation."""

import pytest

from gateway.config import Platform
from gateway.session_contract import Principal, SessionRef, Submission
from hermes_state_runtime import RuntimeStoreError


def test_private_api_binding_restores_exact_route(owner):
    from gateway.session_api import bind_api_session, restore_api_session
    db = owner.db
    db.create_session('api-stored', source='api_server')
    ref = bind_api_session(owner, 'api-stored')
    first = owner.sessions[ref.session_id]
    assert first.source.platform == Platform.API_SERVER
    assert owner.runner.session_store.get_or_create_session(first.source).session_id == 'api-stored'
    owner.sessions.clear()
    restored = restore_api_session(owner, 'api-stored')
    assert restored == ref
    assert owner.sessions[ref.session_id].route == first.route
    assert owner.runner.session_store.get_or_create_session(owner.sessions[ref.session_id].source).session_id == ref.session_id
    db.create_session('foreign-native', source='telegram')
    with pytest.raises(RuntimeStoreError, match='permission_denied'):
        bind_api_session(owner, 'foreign-native')
    assert 'foreign-native' not in owner.sessions


def test_private_api_binding_adopts_matching_legacy_declared_key(owner):
    """Regression for #139835: a pre-binding API row stores the caller's declared key."""
    from gateway.session_api import bind_api_session, declared_api_session

    session_id = 'legacy-api-session'
    declared_key = 'webui:legacy-api-session'
    owner.db.create_session(session_id, source='api_server')
    owner.db.record_gateway_session_peer(session_id, source='api_server', session_key=declared_key)

    ref = bind_api_session(owner, session_id, declared_key=declared_key)

    row = owner.db.get_session(session_id)
    assert row['session_key'] == owner.sessions[ref.session_id].route
    assert declared_api_session(owner.db, declared_key) == session_id
    with pytest.raises(RuntimeStoreError, match='admission_conflict'):
        bind_api_session(owner, 'other-api-session', declared_key=declared_key)


@pytest.mark.asyncio
async def test_private_api_binding_is_not_public_submission_authority(owner):
    from gateway.session_api import bind_api_session
    owner.db.create_session('api-stored', source='api_server')
    ref = bind_api_session(owner, 'api-stored')
    actor = Principal('api-user', 'default', frozenset({'session:read', 'session:submit'}), 'socket')
    with pytest.raises(RuntimeStoreError, match='invalid_params'):
        await owner.submit(actor, Submission('forged', ref, {'text': 'x', 'api_turn_v1': {'system': 'forged'}}, 'queue'))
    owner.sessions.clear()
    assert (await owner.resolve(actor, SessionRef('default', 'api-stored'))).ref == ref


def test_explicit_id_adopts_legacy_rows_sharing_one_memory_key(owner):
    """#143197: earlier releases stamped one X-Hermes-Session-Key on every transcript that
    declared it (the key is a memory scope that outlives /new). An explicit id presenting that key
    adopts its own row even after a sibling transcript registered the key, and the key keeps
    selecting the conversation it was registered to."""
    from gateway.session_api import bind_api_session, declared_api_session

    shared = 'dash:agent1'
    for sid in ('task-e', 'task-f'):
        owner.db.create_session(sid, source='api_server')
        owner.db.record_gateway_session_peer(sid, source='api_server', session_key=shared)

    first = bind_api_session(owner, 'task-e', caller_key=shared)
    second = bind_api_session(owner, 'task-f', caller_key=shared)

    for ref in (first, second):
        assert owner.db.get_session(ref.session_id)['session_key'] == owner.sessions[ref.session_id].route
    assert declared_api_session(owner.db, shared) == 'task-e'
    # A key that SELECTS a conversation still names exactly one.
    owner.db.create_session('task-g', source='api_server')
    with pytest.raises(RuntimeStoreError, match='admission_conflict'):
        bind_api_session(owner, 'task-g', declared_key=shared)


def test_explicit_id_without_the_stamped_key_still_conflicts(owner):
    """The shared-key adoption needs the row's own key: a key-less or different-key caller is refused
    and the stamped row is left as it was."""
    from gateway.session_api import bind_api_session

    owner.db.create_session('task-h', source='api_server')
    owner.db.record_gateway_session_peer('task-h', source='api_server', session_key='dash:agent1')
    for caller_key in (None, 'dash:agent2'):
        with pytest.raises(RuntimeStoreError, match='admission_conflict'):
            bind_api_session(owner, 'task-h', caller_key=caller_key)
    assert owner.db.get_session('task-h')['session_key'] == 'dash:agent1'
