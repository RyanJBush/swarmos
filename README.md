# SwarmOS

## Phase 1: bounded coding controller

SwarmOS Phase 1 implements a deterministic controller with three roles:

- **Planner** can inspect the workspace and propose a plan.
- **Implementer** can make one validated patch attempt.
- **Reviewer** can inspect the workspace and run the fixed `pytest` action.

The controller enforces role-specific tool allowlists, planner-to-reviewer role
ordering, a maximum of 8 steps, and a maximum of 1 patch attempt. Unauthorized
tools, unsafe paths, invalid operations, and failed actions terminate the run
with an explicit code. SWARM-001 uses a disposable Git fixture and one
deterministic implementation for `src/labels.py`; the reviewer requires a real
Git diff and passing acceptance evidence outside the fixture.

Run the deterministic evidence demo:

```powershell
.\.venv\Scripts\python.exe -m swarmos demo --output evidence/my-demo
```

The command writes `run-summary.json` and `swarm001.diff` with the roles, tools,
bounded results, termination code, and actual fixture diff. Run tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Phase 2A: persistent run history

Each demo run is also recorded in the existing SQLite persistence layer. The
default database is `.swarmos/runs.sqlite3`; use `--database` to select another
project-local path:

```powershell
.\.venv\Scripts\python.exe -m swarmos demo `
  --output evidence/my-demo --database .swarmos\runs.sqlite3
.\.venv\Scripts\python.exe -m swarmos inspect `
  --run-id <run-id> --database .swarmos\runs.sqlite3
.\.venv\Scripts\python.exe -m swarmos list --database .swarmos\runs.sqlite3
```

The demo prints the run ID. `inspect` shows the persisted status, timestamps,
five ordered controller steps on success, and the termination event. Failed
and repeated runs are stored as failed runs and return a nonzero exit status.
Existing evidence files are preserved; later runs use run-specific filenames.
SQLite databases and generated evidence are excluded from Git. Persistence is
run history, not reusable agent memory, and this phase still has no MCP,
dashboard, or real-LLM execution.

This is simulated role behavior, not a real LLM coding agent. It has no shell
execution, network access, credential access, arbitrary repository writes,
persistent memory, MCP integration, observability dashboard, or real LLM
integration. The deterministic prototype must not be represented as a secure
real-model coding agent. The only subprocesses are fixed `git` and `pytest`
commands used by the trusted fixture workflow.

The fixture now implements the deterministic SWARM-001
`normalize_label(text: str) -> str` behavior: trimming, ASCII-compatible
lowercasing, internal whitespace replacement, underscore preservation, Unicode
preservation, and empty-input rejection.

The fixture must be created at a new, unused path by the controller and carries
a controller-owned marker. Acceptance is pinned by canonical path and SHA-256
content, and requires exactly one passed test with zero skips. These checks are
application-level validation only; Windows filesystem checks remain vulnerable
to time-of-check/time-of-use races and do not provide OS-enforced sandbox
confinement. Pytest output parsing and application-level fixture ownership are
also validation signals, not security boundaries for untrusted generated code.
