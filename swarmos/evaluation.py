"""Paired repeat-task evaluation, not an autonomous coding benchmark."""
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
from uuid import uuid4
from .controller import create_swarm001_fixture
from .execution import execute
from .run_history import RunHistory


def evaluate(output, trials=3):
    if not 1 <= trials <= 20:
        raise ValueError('trials must be between 1 and 20')
    root = Path(output).resolve() / ('evaluation-' + uuid4().hex)
    root.mkdir(parents=True)
    baseline = root / 'unpatched'
    create_swarm001_fixture(baseline)
    test = Path(__file__).parent.parent / 'tests' / 'test_swarm001_acceptance.py'
    raw = subprocess.run([sys.executable, '-m', 'pytest', '-q', str(test)],
        cwd=test.parent.parent, env={**os.environ, 'SWARM001_FIXTURE_ROOT': str(baseline)},
        capture_output=True, text=True, timeout=30)
    if raw.returncode != 1 or '1 failed' not in raw.stdout:
        raise RuntimeError('unpatched baseline did not demonstrate the expected acceptance failure')
    records = []
    with RunHistory(root / 'runs.sqlite3') as h:
        # Separate warmup per arm; off never reads or writes memory.
        warmups = [execute(h, root, 'off', False), execute(h, root, 'on', True)]
        for trial in range(trials):
            for enabled in ([False, True] if trial % 2 == 0 else [True, False]):
                records.append(execute(h, root, 'on' if enabled else 'off', enabled))
    summary = {}
    for enabled in (False, True):
        rows = [r for r in records if r['memory_enabled'] == enabled]
        summary['on' if enabled else 'off'] = {
            'runs': len(rows), 'successes': sum(r['completed'] for r in rows),
            'memory_hits': sum(r['memory_hit'] for r in rows),
            'median_execution_ms': statistics.median(r['execution_ms'] for r in rows),
            'mean_steps': statistics.mean(len(r['steps']) for r in rows),
            'patch_attempts': sum(r['patches_attempted'] for r in rows)}
    report = {'benchmark': 'SWARM-001 repeated deterministic fixture', 'trials_per_arm': trials,
        'limitations': 'Same task and fixed patch; warm memory provides advisory context only. No claim of coding generalization or causal latency benefit.',
        'unpatched_baseline': {'returncode': raw.returncode, 'stdout': raw.stdout, 'stderr': raw.stderr},
        'warmup_run_ids': [r['run_id'] for r in warmups], 'summary': summary, 'runs': records}
    path = root / 'evaluation.json'
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return path, report
