"""An operator's pause is never replaced, and so never lifted, by cron receipt recovery.

``pause_for_unknown`` (the firer's ``CronExecutionUnknown`` handler) and ``reconcile_pending``'s own
``unknown`` branch pause a job whose admission could not be verified, then resume it once a receipt
proves the run terminal, but only "iff it is still held by exactly that pause". When the operator
had ALREADY paused the job (typically mid-run, then restarted the gateway), the recovery pause
overwrote ``paused_at``/``paused_reason`` and became the pause recovery owned, so the terminal
receipt resumed a job the operator had stopped (#145596)."""
from contextlib import asynccontextmanager
import json

from cron import executions, jobs, scheduler, scheduler_authority
from hermes_cli import gateway_client


def _peer(monkeypatch, answer):
    class Peer:
        async def rpc(self, method, **params):
            return answer(method)

    @asynccontextmanager
    async def connected():
        yield Peer()
    monkeypatch.setattr(gateway_client, 'connect_gateway', connected)


def _journal(job, fire):
    journal = scheduler_authority.journal_path(job['id'], fire)
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(json.dumps({'params': {'job_id': job['id'], 'request_id': fire,
                                              'extra_prompt': None}, 'receipt': None}), encoding='utf-8')
    return journal


def _fire_lost_after_operator_pause(monkeypatch, job, fire):
    """The operator pauses the job while its fire is in flight; the observer then drops."""
    journal = scheduler_authority.journal_path(job['id'], fire)

    def run_job(job, **kwargs):
        _journal(job, fire)
        jobs.pause_job(job['id'], reason='operator hold')
        raise scheduler_authority.CronExecutionUnknown('Cron execution unverified: observer dropped')
    monkeypatch.setattr(scheduler, 'run_job', run_job)
    assert scheduler._run_one_job_body(dict(jobs.get_job(job['id']), execution_id=fire)) is False
    return journal


def _operator_pause(saved):
    return saved['state'], saved['enabled'], saved['paused_reason']


def test_unknown_fire_keeps_the_operators_pause_and_the_receipt_does_not_lift_it(tmp_path, monkeypatch):
    with jobs.use_cron_store(tmp_path / 'cron'):
        job = jobs.create_job(prompt='report', schedule='every 1h', deliver='local')
        fire = executions.create_execution(job['id'], source='test')['id']
        journal = _fire_lost_after_operator_pause(monkeypatch, job, fire)
        held = jobs.get_job(job['id'])
        # The firer's unverified-admission pause must not replace the operator's pause record.
        assert _operator_pause(held) == ('paused', False, 'operator hold')
        assert 'pause_recorded' not in json.loads(journal.read_text(encoding='utf-8-sig'))

        _peer(monkeypatch, lambda method: {'status': 'terminal', 'job': job,
                                           'result': [True, 'document', 'answer', None]})
        scheduler_authority.reconcile_pending()

        saved = jobs.get_job(job['id'])
        assert _operator_pause(saved) == ('paused', False, 'operator hold')
        assert saved['paused_at'] == held['paused_at']
        assert executions.get_execution(fire)['status'] == 'completed'
        assert not journal.exists()


def test_reconcile_unknown_verdict_does_not_take_over_an_operator_pause(tmp_path, monkeypatch):
    with jobs.use_cron_store(tmp_path / 'cron'):
        job = jobs.create_job(prompt='report', schedule='every 1h', deliver='local')
        fire = executions.create_execution(job['id'], source='test')['id']
        executions.mark_execution_running(fire)
        with executions._transaction() as conn:
            conn.execute('UPDATE executions SET process_id=?,pid=? WHERE id=?', ('old-owner', 999999, fire))
        journal = _journal(job, fire)
        jobs.pause_job(job['id'], reason='operator hold')
        held = jobs.get_job(job['id'])

        _peer(monkeypatch, lambda method: {'status': 'unknown', 'result': None})
        scheduler_authority.reconcile_pending()
        assert _operator_pause(jobs.get_job(job['id'])) == ('paused', False, 'operator hold')

        _peer(monkeypatch, lambda method: {'status': 'terminal', 'job': job,
                                           'result': [True, 'document', 'answer', None]})
        scheduler_authority.reconcile_pending()

        saved = jobs.get_job(job['id'])
        assert _operator_pause(saved) == ('paused', False, 'operator hold')
        assert saved['paused_at'] == held['paused_at']
        assert not journal.exists()


def test_unknown_fire_still_pauses_a_running_job_and_the_receipt_still_lifts_it(tmp_path, monkeypatch):
    """The recovery pause on an unpaused job keeps its contract (see test_cron_recover_pause)."""
    with jobs.use_cron_store(tmp_path / 'cron'):
        job = jobs.create_job(prompt='report', schedule='every 1h', deliver='local')
        fire = executions.create_execution(job['id'], source='test')['id']

        def run_job(job, **kwargs):
            _journal(job, fire)
            raise scheduler_authority.CronExecutionUnknown('Cron execution unverified: observer dropped')
        monkeypatch.setattr(scheduler, 'run_job', run_job)
        assert scheduler._run_one_job_body(dict(jobs.get_job(job['id']), execution_id=fire)) is False
        paused = jobs.get_job(job['id'])
        assert paused['state'] == 'paused' and paused['enabled'] is False
        assert 'observer dropped' in paused['paused_reason']

        _peer(monkeypatch, lambda method: {'status': 'terminal', 'job': job,
                                           'result': [True, 'document', 'answer', None]})
        scheduler_authority.reconcile_pending()
        saved = jobs.get_job(job['id'])
        assert (saved['state'], saved['enabled'], saved['paused_reason']) == ('scheduled', True, None)
