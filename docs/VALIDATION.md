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

At the initial local checkpoint, no remote repository had been created and no push had occurred. See the publication addendum below for subsequent authorized work.
No full protocol-conformance, live LLM, adversarial sandbox, or external client
compatibility claim is made. Publication should include a license decision and
remote CI verification after the owner authorizes pushing.

Final suite: **48 passed, 1 skipped in 21.96 s** using the isolated local environment. git diff --check completed successfully.

Publication audit found ignored generated evidence and bytecode in inherited pre-checkpoint history. A separate publication repository imports the clean checkpoint tree and replays the focused development commits; the full original history is preserved in the development checkout. No inherited generated artifact is reachable from the publication branch.

A later clean-publication-checkout test exposed a second long-path case at Git initialization (47 passed, 1 failed, 1 skipped). Fixtures were moved to short project-local `.swarmos/work/` paths; the final clean-checkout result below supersedes that failed attempt.

Final clean publication checkout after the fixture-path fix: **48 passed, 1 skipped in 23.53 s**. A fresh three-trial evaluation passed 3/3 per arm, with 0 versus 3 memory hits and five steps per run. Median execution times were 936.650 ms (off) and 937.184 ms (on), illustrating why no latency improvement is claimed. Report: `evidence/final/evaluation-bc51009b5d0846e08ab4288967ffef25/evaluation.json` in the publication checkout.

## Authorized private publication and CI

On November 7, 2026 (America/New_York), the owner approved creation and publication
of `RyanJBush/swarmos` as a **private** repository. All seven prepared commit objects
were transferred through the authenticated GitHub API, with every tree and commit
SHA checked against the local checkout. Implementation HEAD: `bd4dd2d01f90e4445524d5caa2a99ec5ed0a9305`.

[GitHub Actions run 42434894375](https://github.com/RyanJBush/swarmos/actions/runs/42434894375)
passed all four matrix jobs: Windows and Ubuntu, each on Python 3.11 and 3.13.
Each job completed a clean dependency installation, pytest suite, deterministic demo,
and one-trial-per-arm memory evaluation. No workflow failures remained.
This verifies the configured CI environments; it does not establish live LLM client
compatibility, autonomous coding performance, or sandbox isolation.

The follow-up documentation-only commit records these results and uses `[skip ci]`;
it does not change the tested implementation. The repository remains private.
