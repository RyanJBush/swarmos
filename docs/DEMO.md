# Recorded demonstration

Watch [the 2-minute-52-second captioned recording](media/swarmos-demo.webm) and inspect
[the actual metrics used in it](media/demo-evidence.json). The screenshot in the
README is captured from the generated run timeline. These curated presentation
assets are intentionally versioned; raw runtime evidence and databases remain ignored.

## Regenerate the recording

Optional tooling: Node.js, Playwright, and its Chromium/FFmpeg downloads.
These are presentation tools, not runtime dependencies. From the checkout:

```powershell
npm install --no-save --package-lock=false playwright
npx playwright install chromium
node scripts/record_demo.cjs .venv/Scripts/python.exe
```

The script executes two real memory-enabled runs in a fresh project, a separate
three-trial paired evaluation and an evidence verification. It then records a local
browser walkthrough of those captured results. Runtime is about three minutes.
It uses no voice synthesis, model API, remote page, or credentials. On Linux/macOS,
pass `.venv/bin/python`. GitHub may offer WebM as a download; open it in a browser.

# Three-minute demonstration

From the repository root, with dependencies installed:

1. Run `.venv\Scripts\python.exe -m swarmos demo --project recruiter-demo --memory on`.
   Open the printed timeline file. Show the five roles/tools, measured durations,
   real diff and successful review decision. Say that the patch is deterministic.
2. Repeat the command. Show `Memory hit: True`, then inspect that run. Explain that
   memory supplies a bounded advisory fact and cannot skip the acceptance gate.
3. Run `.venv\Scripts\python.exe -m swarmos evaluate --trials 3 --output evidence/benchmark`.
   Show the unpatched failure and the two successful arms. Discuss equal tool counts
   and the limited meaning of timing measurements on one repeated task.
4. Run `verify --run-id RUN_ID`. Optionally edit the exported diff, observe verification
   fail, then run `export --run-id RUN_ID` and verify again. SQLite is authoritative.
5. Show `examples/proposal.json`, its digest approval and the single read-only MCP tool.

The full test suite is `.venv\Scripts\python.exe -m pytest tests -q`.
One standalone acceptance skip is expected without `SWARM001_FIXTURE_ROOT`; the
controller and evaluation tests run that same test in real fixture subprocesses.

If this constrained development session cannot write pytest's default temporary
directory, use `--basetemp .pytest-tmp-demo`. Pytest owns and cleans the directory
specified by `--basetemp`; use a disposable directory only.

## Honest resume wording

- Built a bounded Planner–Implementer–Reviewer workflow with atomic SQLite run
  finalization, timed execution traces, repairable evidence exports, and offline
  run timelines.
- Added project-scoped advisory memory, a paired memory-on/off fixture evaluation,
  digest-approved proposal handoffs, and a read-only MCP inspection interface.

Attach actual test counts and evaluation results only with their scope and evidence.
Do not describe this implementation as a sandboxed autonomous coding agent.

The published recording was checked in Chromium: 172 seconds, 1440×900. It was compressed to one frame per second for these mostly static evidence screens. Scene hold times total 150 seconds; browser rendering adds overhead. The original recording remains in ignored local evidence.
