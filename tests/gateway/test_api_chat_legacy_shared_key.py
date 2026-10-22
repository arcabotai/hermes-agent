"""#143197: API transcripts an earlier release wrote under one shared ``X-Hermes-Session-Key`` (the
documented memory scope that outlives ``/new``) each carry that key in ``sessions.session_key``.
After an upgrade every one of them must keep answering ``/v1/chat/completions`` on its own
``X-Hermes-Session-Id``, not just the first one the canonical binding adopted."""
import json
import os
import subprocess
import sys
from pathlib import Path


def test_chat_completions_continue_every_transcript_of_a_shared_legacy_key(tmp_path):
    result = subprocess.run([sys.executable, __file__], cwd=Path(__file__).resolve().parents[2],
        env=dict(os.environ, HERMES_HOME=str(tmp_path)), capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    print((tmp_path / 'shared-key-receipt.json').read_text(encoding='utf-8-sig'))


async def _stub_llm():
    """Loopback OpenAI-compatible model: one fixed reply, JSON or SSE."""
    from aiohttp import web

    async def completions(request):
        body = await request.json()
        reply = {'role': 'assistant', 'content': 'stub reply'}
        if not body.get('stream'):
            return web.json_response({'id': 'c', 'object': 'chat.completion', 'created': 0, 'model': 'stub',
                'choices': [{'index': 0, 'message': reply, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}})
        response = web.StreamResponse(headers={'Content-Type': 'text/event-stream'})
        await response.prepare(request)
        for delta, finish in ((reply, None), ({}, 'stop')):
            chunk = {'id': 'c', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'stub',
                     'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}]}
            await response.write(b'data: ' + json.dumps(chunk).encode() + b'\n\n')
        await response.write(b'data: [DONE]\n\n')
        return response

    app = web.Application()
    app.router.add_post('/v1/chat/completions', completions)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    return runner, site._server.sockets[0].getsockname()[1]


async def probe(llm_port):
    import aiohttp
    from gateway.config import Platform, PlatformConfig
    from gateway.platforms.api_server import APIServerAdapter
    from gateway.run import GatewayRunner
    from gateway.session_api import declared_api_session
    from gateway.session_authority import initialize_session_authority

    runner = GatewayRunner()
    authority = await initialize_session_authority(runner, profile_id='default', instance_id='shared-key-test')
    db = authority.db
    shared = 'dash:agent1'
    # Rows exactly as an earlier release left them: the shared key verbatim, no binding receipt.
    for sid in ('task-e', 'task-f', 'task-h'):
        db.create_session(sid, source='api_server')
        db.record_gateway_session_peer(sid, source='api_server', session_key=shared)
    adapter = APIServerAdapter(PlatformConfig(enabled=True, extra={'key': 'shared-key-probe-secret', 'port': 0}))
    adapter.gateway_runner = runner
    adapter.set_message_handler(runner._handle_message)
    runner.adapters[Platform.API_SERVER] = adapter
    assert await adapter.connect()
    port = adapter._site._server.sockets[0].getsockname()[1]
    out = {}

    async def chat(client, name, session_id, key):
        headers = {'Authorization': 'Bearer shared-key-probe-secret', 'X-Hermes-Session-Id': session_id}
        if key:
            headers['X-Hermes-Session-Key'] = key
        body = {'model': 'hermes-agent', 'messages': [{'role': 'user', 'content': name}]}
        async with client.post(f'http://127.0.0.1:{port}/v1/chat/completions', json=body, headers=headers) as response:
            payload = await response.json()
            out[name] = [response.status, response.headers.get('X-Hermes-Session-Id'), payload]
            return response.status, response.headers.get('X-Hermes-Session-Id'), payload
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as client:
            for name, sid in (('e-1', 'task-e'), ('f-1', 'task-f'), ('f-2', 'task-f')):
                status, echoed, payload = await chat(client, name, sid, shared)
                assert status == 200, (name, status, payload)
                assert echoed == sid, (name, echoed)
            # Without the stamped key the explicit id still proves nothing about the row.
            status, _, payload = await chat(client, 'h-keyless', 'task-h', None)
            assert status == 409 and payload['error']['code'] == 'admission_conflict', (status, payload)
        route = lambda sid: db.get_session(sid)['session_key']
        assert route('task-f') == 'agent:main:api_server:dm:task-f', route('task-f')
        assert route('task-h') == shared, 'a refused caller must not rewrite the row'
        # Both continued turns landed on the caller's transcript: no implicit api-* session appeared.
        user_turns = [m for m in db.get_messages_as_conversation('task-f') if m.get('role') == 'user']
        assert [m['content'] for m in user_turns] == ['f-1', 'f-2'], user_turns
        assert not [s for s in db.list_sessions_rich(limit=50) if str(s.get('id', '')).startswith('api-')]
        # The key keeps selecting the conversation that registered it first.
        assert declared_api_session(db, shared) == 'task-e'
        Path(os.environ['HERMES_HOME'], 'shared-key-receipt.json').write_text(encoding='utf-8', data=json.dumps(out))
    finally:
        await adapter.disconnect()


async def main():
    llm, llm_port = await _stub_llm()
    try:
        Path(os.environ['HERMES_HOME'], 'config.yaml').write_text(
            f'model:\n  default: stub\n  provider: custom\n  base_url: http://127.0.0.1:{llm_port}/v1\n'
            'auxiliary:\n  title_generation:\n    enabled: false\n')
        os.environ.update(OPENAI_API_KEY='loopback-only', OPENAI_BASE_URL=f'http://127.0.0.1:{llm_port}/v1')
        await probe(llm_port)
    finally:
        await llm.cleanup()


if __name__ == '__main__':
    import asyncio
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    asyncio.run(main())
