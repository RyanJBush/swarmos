"""One execution service shared by CLI and paired evaluations."""
from pathlib import Path
from time import perf_counter
from .controller import ControllerResult, TerminationCode, run_swarm001
from .memory import Memory
from . import evidence
from .timeline import render


def execute(history, output, project, memory_enabled=False, operations=None, proposal_digest=None):
    memory = Memory(history, project)
    recalled = memory.recall() if memory_enabled else None
    run = history.start()
    started = perf_counter()
    try:
        result = run_swarm001(Path(output).resolve() / run.id / 'fixture',
            Path(__file__).parent.parent / 'tests' / 'test_swarm001_acceptance.py',
            operations=operations, memory_hint=('; advisory: ' + recalled['content']) if recalled else '')
    except Exception as error:
        result = ControllerResult(TerminationCode.OPERATION_FAILED, (), 0,
            f'unexpected execution failure: {type(error).__name__}: {error}')
    data = evidence.payload(run, result)
    data.update(project=project, proposal_sha256=proposal_digest, memory_enabled=memory_enabled,
                memory_hit=recalled is not None,
                memory_source_run=recalled['source_run'] if recalled else None,
                execution_ms=round((perf_counter() - started) * 1000, 3))
    history.finish(run, result, data)
    if memory_enabled and result.completed:
        memory.remember(run.id)
    evidence.export(history, run.id, output)
    render(history, run.id, output)
    return data
