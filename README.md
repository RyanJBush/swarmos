# SwarmOS

**A bounded coding-workflow demonstrator with durable, inspectable evidence.**

SwarmOS runs Planner → Implementer → Reviewer against a disposable Git repository.
A fixed SWARM-001 patch must produce a real diff and pass the trusted acceptance
test before the controller approves the run. SQLite records results, timed traces,
and project-scoped advisory memory; an offline HTML timeline makes each run inspectable.

This is a deterministic agent-workflow engineering MVP. It does **not** generate
arbitrary code, use an LLM, or provide an operating-system sandbox. The planner's
inspection action is currently a validated path acknowledgement, not semantic repo analysis.

## Quick start

Requirements: Git on PATH and Python 3.11+. Run commands from this source checkout;
the reviewer deliberately uses the trusted test file in `tests/`.
No API key, cloud account, Docker, or paid service is required.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m swarmos demo --project portfolio --memory on
```

On macOS/Linux use `.venv/bin/python` instead of `.venv\Scripts\python.exe`.
The CLI prints a run ID and a `timeline.html` path. Open that file in your browser.
Run the demo again to observe a memory hit with the same five review-gated steps.
The default is memory **off**; use a stable `--project` identifier to scope memory.

## Inspect and recover

Replace `RUN_ID` with the printed UUID. All commands accept `--database PATH` and
`--output DIRECTORY`; defaults are `.swarmos/runs.sqlite3` and `evidence/demo`.

```powershell
.\.venv\Scripts\python.exe -m swarmos list
.\.venv\Scripts\python.exe -m swarmos inspect --run-id RUN_ID
.\.venv\Scripts\python.exe -m swarmos verify --run-id RUN_ID
.\.venv\Scripts\python.exe -m swarmos export --run-id RUN_ID
.\.venv\Scripts\python.exe -m swarmos timeline --run-id RUN_ID
.\.venv\Scripts\python.exe -m swarmos memory-clear --project portfolio
```

Run metadata, steps, traces, termination, and the evidence payload finalize in one
transaction. Exported JSON/diff files are derived copies, with a manifest published
last. `verify` compares them against SQLite; `export` repairs missing or altered
copies. Successful execution does not imply successful export. A failed export
returns a nonzero exit status and identifies the durable run for retry.

A process killed before finalization leaves a `running` row. After confirming that
its process has stopped, explicitly mark it failed with `recover --run-id RUN_ID`.
Partial in-flight steps are not recoverable; this MVP records traces at finalization.
Do not recover a live run. Older checkpoint runs have no durable evidence payload;
they remain inspectable but cannot be exported retroactively.

## Evaluate

```powershell
.\.venv\Scripts\python.exe -m swarmos evaluate --trials 3 --output evidence/benchmark
```

The evaluator checks an unpatched fixture baseline, warms two independent arms,
alternates memory-on/off execution order, and saves raw run evidence plus metrics.
Memory-on and memory-off use the same fixed patch and acceptance gates. Memory can
show persistence and retrieval, but this design does not demonstrate better coding
quality or fewer tool calls. See [measured results](docs/VALIDATION.md).

## Bounded integrations

An external assistant can propose the five JSON operations in
[examples/proposal.json](examples/proposal.json). Review the exact file, then approve
its SHA-256 digest. The digest binds approval to those bytes; unknown fields, changed
roles, arbitrary commands, and arbitrary patches are rejected before execution.

```powershell
$proposalHash = (Get-FileHash examples/proposal.json -Algorithm SHA256).Hash.ToLower()
.\.venv\Scripts\python.exe -m swarmos demo --project portfolio --proposal examples/proposal.json --approve-proposal $proposalHash
```

Computing a hash is not a substitute for reviewing the file. This is an offline
handoff adapter, not a verified live Claude/OpenAI/Ollama integration.

A minimal read-only MCP stdio server exposes **only `inspect_run`** in the configured
project. It opens SQLite read-only, has bounded input/output sizes, and cannot run
the controller, read arbitrary files, alter memory, or install tools.

```powershell
.\.venv\Scripts\python.exe -m swarmos mcp --project portfolio --database .swarmos/runs.sqlite3
```

Configure an MCP client to launch that command from this checkout. It implements
the pinned **2025-11-25** initialization/tools subset; no claim of full protocol
conformance or compatibility with every client is made. See [integration details](docs/INTEGRATIONS.md).

## Engineering evidence

- Eight-step ceiling, one patch attempt, role allowlists, exact completion sequence.
- Trusted acceptance file integrity check, actual Git diff and pytest subprocess.
- Transaction rollback, restart, concurrent initialization, export repair tests.
- Project isolation, memory-off control, rejected-operation tracing, escaped HTML.
- CI matrix for Windows/Linux and Python 3.11/3.13; remote CI awaits publication.

Read the [architecture](docs/ARCHITECTURE.md), [security boundaries](SECURITY.md),
[validation record](docs/VALIDATION.md), and [three-minute demo](docs/DEMO.md).

## Publication status

Continues checkpoint `eff728e2c3d5d1355c0271036202e034e62a0ef6`.
Local focused commits are prepared; no GitHub repository has been created or pushed
by this development session. Publication requires the owner's approval.
Generated evidence, local databases and journals, credentials, and environments
are excluded by `.gitignore`. No license is selected yet; choose one before
advertising the project as open source.
