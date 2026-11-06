"""Live local restore must ignore per-turn message_id (#143537)."""
import pytest

from tests.gateway.test_local_recovery_pre_profile_origin import _served_authority


@pytest.mark.asyncio
async def test_live_local_restore_ignores_stamped_message_id(tmp_path, monkeypatch):
    from gateway.session_contract import SessionActor
    from gateway.session_local import create_local_session
    from gateway.session_local_recovery import restore_local_session
    from hermes_state_runtime import RuntimeStoreError

    served, _db, secondary = await _served_authority(tmp_path, monkeypatch, 'first')
    actor = SessionActor('owner', str(secondary), frozenset({'session:create', 'session:read'}), 'socket')
    ref = create_local_session(
        served, actor,
        {'request_id': 'turn1', 'source': 'gui', 'cwd': str(tmp_path), 'model': 'frozen', 'toolsets': []},
    )
    live = served.sessions[ref.session_id]
    # First turn stamps the triggering message onto the live source (desktop/TUI path).
    live.source.message_id = '20eedc39854645e99186b4186bcb18eb'

    assert restore_local_session(served, ref.session_id) == ref
    assert live.source.message_id == '20eedc39854645e99186b4186bcb18eb'

    # Genuine identity drift still refuses.
    live.source.user_id = 'uid:tampered'
    with pytest.raises(RuntimeStoreError, match='storage_unavailable'):
        restore_local_session(served, ref.session_id)


def test_kept_source_reuses_admission_when_only_message_id_differs():
    from gateway.config import Platform
    from gateway.session import SessionSource
    from gateway.session_local import LocalSessionAdapter
    from types import SimpleNamespace

    authority = SimpleNamespace(sessions={})
    adapter = LocalSessionAdapter(authority)
    admitted = SessionSource(platform=Platform.LOCAL, chat_id='local-1', user_id='uid:1', chat_type='dm')
    adapter.register_source(admitted)
    authority.sessions['local-1'] = SimpleNamespace(source=admitted)

    claim = SessionSource(platform=Platform.LOCAL, chat_id='local-1', user_id='uid:1', chat_type='dm',
                          message_id='abc123')
    assert adapter.kept_source(claim) is admitted
