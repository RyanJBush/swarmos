import pytest
from swarmos.run_history import RunHistory
from swarmos import evidence
from test_run_history import _result


def test_finish_rollback_and_retry(tmp_path, monkeypatch):
    with RunHistory(tmp_path / 'db') as h:
        run = h.start()
        original = h.runs.add_event
        monkeypatch.setattr(h.runs, 'add_event', lambda *a: (_ for _ in ()).throw(OSError('injected')))
        with pytest.raises(OSError):
            h.finish(run, _result())
        current, tasks, events = h.get(run.id)
        assert current.status == 'running' and not tasks and not events
        assert h.database.connection.execute('SELECT count(*) FROM swarmos_agents').fetchone()[0] == 0
        monkeypatch.setattr(h.runs, 'add_event', original)
        h.finish(run, _result())
        with pytest.raises(ValueError):
            h.finish(run, _result())


def test_successful_prefix_stays_successful(tmp_path):
    with RunHistory(tmp_path / 'db') as h:
        run = h.start()
        h.finish(run, _result(False))
        assert all(t.status == 'succeeded' for t in h.get(run.id)[1])


def test_export_recovery_and_tampering(tmp_path, monkeypatch):
    with RunHistory(tmp_path / 'db') as h:
        run = h.start()
        result = _result()
        h.finish(run, result, evidence.payload(run, result))
        real = evidence.os.replace
        monkeypatch.setattr(evidence.os, 'replace', lambda *a: (_ for _ in ()).throw(OSError('disk full')))
        with pytest.raises(OSError):
            evidence.export(h, run.id, tmp_path / 'out')
        assert evidence.stored(h, run.id)['completed']
        with pytest.raises(FileNotFoundError):
            evidence.verify(h, run.id, tmp_path / 'out')
        monkeypatch.setattr(evidence.os, 'replace', real)
        root = evidence.export(h, run.id, tmp_path / 'out')
        (root / 'swarm001.diff').write_text('tampered')
        with pytest.raises(ValueError, match='mismatch'):
            evidence.verify(h, run.id, tmp_path / 'out')
        evidence.export(h, run.id, tmp_path / 'out')
        assert evidence.verify(h, run.id, tmp_path / 'out')


def test_interrupt_rolls_back(tmp_path):
    with RunHistory(tmp_path / 'db') as h:
        with pytest.raises(KeyboardInterrupt):
            with h.database.transaction():
                h.workflows.create('interrupted')
                raise KeyboardInterrupt
        assert h.workflows.get_by_name('interrupted') is None
