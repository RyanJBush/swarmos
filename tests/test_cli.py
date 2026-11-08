import json
import subprocess
import sys
import pytest
from swarmos import execution, evidence
from swarmos.run_history import RunHistory


def test_unexpected_execution_failure_persisted(tmp_path, monkeypatch):
    monkeypatch.setattr(execution, 'run_swarm001', lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('injected')))
    with RunHistory(tmp_path / 'db') as h:
        data = execution.execute(h, tmp_path / 'out', 'project')
        assert not data['completed']
        assert h.get(data['run_id'])[0].status == 'failed'
        assert evidence.verify(h, data['run_id'], tmp_path / 'out')


def test_cli_repeated_demo_and_inspection(tmp_path):
    base = [sys.executable, '-m', 'swarmos']
    options = ['--database', str(tmp_path / 'db'), '--output', str(tmp_path / 'out')]
    run_ids = []
    for _ in range(2):
        p = subprocess.run(base + ['demo'] + options, text=True, capture_output=True, timeout=30)
        assert p.returncode == 0, p.stderr
        run_ids.append(p.stdout.split('Run ID: ')[1].splitlines()[0])
    assert run_ids[0] != run_ids[1]
    for command in ('inspect', 'verify', 'export', 'timeline'):
        p = subprocess.run(base + [command, '--run-id', run_ids[0]] + options, text=True, capture_output=True, timeout=10)
        assert p.returncode == 0, p.stderr
    with RunHistory(tmp_path / 'db') as h:
        running = h.start()
    p = subprocess.run(base + ['recover', '--run-id', running.id] + options, text=True, capture_output=True, timeout=10)
    assert p.returncode == 0
    with RunHistory(tmp_path / 'db') as h:
        assert h.get(running.id)[0].status == 'failed'
