"""Project-scoped advisory memory from verified deterministic runs only."""
import json
from .evidence import stored
from .persistence import _now

TASK = 'SWARM-001'


class Memory:
    def __init__(self, history, project):
        if not isinstance(project, str) or not project.strip() or len(project) > 200:
            raise ValueError('project must be a nonempty identifier of at most 200 characters')
        self.history, self.project = history, project

    def recall(self):
        row = self.history.database.connection.execute(
            'SELECT source_run, content FROM swarmos_memory WHERE project=? AND task=?',
            (self.project, TASK)).fetchone()
        if row is None:
            return None
        # Revalidate provenance; memory never grants tool authority.
        source = stored(self.history, row['source_run'])
        if source.get('project') != self.project or not source['completed']:
            raise ValueError('invalid memory provenance')
        return dict(row)

    def remember(self, run_id):
        with self.history.database.transaction():
            run, _, _ = self.history.get(run_id)
            data = stored(self.history, run_id)
            expected = ['inspect_workspace', 'propose_plan', 'apply_patch', 'git_diff', 'run_tests']
            if (run.status != 'succeeded' or not data['completed'] or
                data.get('project') != self.project or
                [s['tool'] for s in data['steps']] != expected or
                data['steps'][-1]['result'] != 'acceptance:passed=1;skipped=0'):
                raise ValueError('memory requires a reviewed successful run in this project')
            # Store a bounded fact, never arbitrary model instructions or executable patches.
            content = json.dumps({'task': TASK, 'fact': 'Fixed normalize_label patch passed trusted acceptance; re-run review for every new run.'})
            self.history.database.connection.execute(
                'INSERT INTO swarmos_memory VALUES (?, ?, ?, ?, ?) ON CONFLICT(project,task) DO UPDATE SET source_run=excluded.source_run, content=excluded.content, created_at=excluded.created_at',
                (self.project, TASK, run_id, content, _now()))

    def clear(self):
        with self.history.database.transaction():
            self.history.database.connection.execute('DELETE FROM swarmos_memory WHERE project=?', (self.project,))
