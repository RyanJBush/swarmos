# Validation record

Development date: November 7, 2026 (America/New_York).
Starting checkpoint: `eff728e2c3d5d1355c0271036202e034e62a0ef6`.
The original local repository was clean and at this checkpoint. Work took place in
a separate copied checkout, preserving its Git history; the original was not edited.

## Audit findings and fixes

| Finding at checkpoint | Change and evidence |
|---|---|
| Finalization autocommitted every statement | One transaction; injected event/status/evidence failures roll back agents, tasks and status |
| Successful DB status preceded fallible evidence writes | Durable payload in finalization; retryable export and byte/hash verification |
| Every step marked failed after a later failure | Completed prefix steps remain successful |
| Duplicate finish could create partial rows | Existing running-state check under write lock |
| Concurrent workflow initialization could race | Serialized lookup/create; eight concurrent start test |
| Acceptance hash depended on CRLF checkout | Normalize line endings for hashing; test contents preserved |
| Repeated CLI output reused a fixture | UUID-specific fixture and evidence paths |
| Long Windows paths broke Git object writes | Per-invocation `core.longpaths=true`; repeated evaluation passed |

## Test milestones

- Original checkpoint: **30 passed, 1 skipped**, 11.81 s.
- Atomic persistence/evidence: **34 passed, 1 skipped**, 11.72 s.
- Traces/timeline: **36 passed, 1 skipped**, 10.54 s.
- Memory/migration: **39 passed, 1 skipped**, 13.99 s.
- Bounded integrations and CLI: **44 passed, 1 skipped**, 17.14 s.
- Transaction concurrency/failure expansion: **47 passed, 1 skipped**, 17.92 s.

Final suite result is recorded below after the paired-evaluation regression test.
The standalone SWARM-001 test skips without its fixture environment variable;
successful controller demos execute it in a subprocess and require one pass and
zero skips. Local platform: Windows, Python 3.13.7, pytest 9.2.0.

The local isolated environment was populated from existing installed project test
packages after a fresh pip download failed DNS/network access. `pip check` passed.
A clean online installation and remote GitHub Actions execution are **not verified**.
CI is configured for Windows/Linux × Python 3.11/3.13, pending publication approval.

## Measured paired evaluation

Report directory: `evidence/benchmark/evaluation-7cac219bd2c740f79203be8b50c613dd/`.
Raw reports and run databases stay local and ignored; regenerate with the documented command.

| Metric | Memory off | Memory on |
|---|---:|---:|
| Measured runs | 3 | 3 |
| Successful runs | 3 | 3 |
| Memory hits | 0 | 3 |
| Mean completed steps | 5 | 5 |
| Total patch attempts | 3 | 3 |
| Median execution time (ms) | 916.173 | 835.579 |

The unpatched baseline returned pytest exit code 1 with one failed acceptance test.
Each arm had a separate warmup excluded from these measurements. Timing includes
fixture creation and the review subprocess, excludes evidence export, and is subject
to OS/process/cache noise. Three repeated runs of one fixed patch are not evidence of
memory improving accuracy, efficiency, or coding generalization.

An earlier report, `evaluation-7c8692159c904c2bbda53a06f5fa2f72`, recorded **0/3 successes
in each arm** due to Windows Git path-length failures. It was retained rather than
relabelled as a successful experiment. The per-command long-path fix preceded the
successful rerun.

## Publication limits

No remote repository was created, no push occurred, and no visibility was changed.
No full protocol-conformance, live LLM, adversarial sandbox, or external client
compatibility claim is made. Publication should include a license decision and
remote CI verification after the owner authorizes pushing.

Final suite: **48 passed, 1 skipped in 21.96 s** using the isolated local environment. git diff --check completed successfully.

Publication audit found ignored generated evidence and bytecode in inherited pre-checkpoint history. A separate publication repository imports the clean checkpoint tree and replays the focused development commits; the full original history is preserved in the development checkout. No inherited generated artifact is reachable from the publication branch.
