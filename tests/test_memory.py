import pytest
from swarmos.run_history import RunHistory
from swarmos.execution import execute
from swarmos.memory import Memory
from swarmos.controller import BoundedController
from swarmos.evidence import payload


def test_memory_restart_isolation_and_off_switch(tmp_path):
    db = tmp_path / 'db'
    with RunHistory(db) as h:
        first = execute(h, tmp_path / 'out', 'a', True)
        assert first['completed'] and not first['memory_hit']
    with RunHistory(db) as h:
        assert Memory(h, 'a').recall()['source_run'] == first['run_id']
        assert Memory(h, 'b').recall() is None
        off = execute(h, tmp_path / 'out', 'a', False)
        assert not off['memory_hit']
        assert Memory(h, 'a').recall()['source_run'] == first['run_id']
        on = execute(h, tmp_path / 'out', 'a', True)
        assert on['memory_hit'] and on['completed']
        assert [s['tool'] for s in on['steps']] == [s['tool'] for s in off['steps']]
        Memory(h, 'b').clear()
        assert Memory(h, 'a').recall()
        Memory(h, 'a').clear()
        assert Memory(h, 'a').recall() is None


def test_failed_run_cannot_seed_memory(tmp_path):
    with RunHistory(tmp_path / 'db') as h:
        run = h.start()
        result = BoundedController().run([])
        data = payload(run, result)
        data['project'] = 'a'
        h.finish(run, result, data)
        with pytest.raises(ValueError):
            Memory(h, 'a').remember(run.id)
        assert Memory(h, 'a').recall() is None


def test_v1_upgrade_preserves_runs(tmp_path, monkeypatch):
    import swarmos.persistence as p
    db = tmp_path / 'db'
    with monkeypatch.context() as patch:
        patch.setattr(p, 'MIGRATIONS', (p.INITIAL_MIGRATION,))
        with RunHistory(db) as h:
            run = h.start()
    with RunHistory(db) as h:
        assert h.get(run.id)[0].status == 'running'
        assert Memory(h, 'a').recall() is None
