import concurrent.futures
import json
import sqlite3
import pytest
from swarmos.run_history import RunHistory
from swarmos.evidence import payload
from test_run_history import _result


def test_concurrent_starts_share_one_workflow(tmp_path):
    db = tmp_path / 'db'
    with RunHistory(db):
        pass
    def start(_):
        with RunHistory(db) as h:
            return h.start().id
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(start, range(8)))
    assert len(set(ids)) == 8
    with RunHistory(db) as h:
        assert h.database.connection.execute('SELECT count(*) FROM swarmos_workflows').fetchone()[0] == 1


def test_final_status_failure_rolls_back_evidence_and_steps(tmp_path, monkeypatch):
    db = tmp_path / 'db'
    with RunHistory(db) as h:
        run = h.start()
        h.database.connection.execute("CREATE TRIGGER reject_finish BEFORE UPDATE ON swarmos_runs BEGIN SELECT RAISE(ABORT, 'injected'); END")
        with pytest.raises(sqlite3.IntegrityError):
            h.finish(run, _result(), payload(run, _result()))
        current, tasks, events = h.get(run.id)
        assert current.status == 'running' and not tasks and not events
        h.database.connection.execute('DROP TRIGGER reject_finish')
        h.finish(run, _result(), payload(run, _result()))
    with RunHistory(db) as h:
        assert h.get(run.id)[0].status == 'succeeded'


def test_evidence_insertion_failure_rolls_back_final_status(tmp_path):
    with RunHistory(tmp_path / 'db') as h:
        run = h.start()
        h.database.connection.execute("CREATE TRIGGER reject_evidence BEFORE INSERT ON swarmos_events WHEN NEW.kind='evidence' BEGIN SELECT RAISE(ABORT, 'injected'); END")
        with pytest.raises(sqlite3.IntegrityError):
            h.finish(run, _result(), payload(run, _result()))
        assert h.get(run.id)[0].status == 'running'
        assert h.get(run.id)[1:] == ([], [])
