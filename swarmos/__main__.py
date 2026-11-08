"""Local CLI; no external service credentials required."""
import argparse
import json
from pathlib import Path
import sys
from .controller import ControllerResult, TerminationCode, run_swarm001
from .run_history import RunHistory
from . import evidence


def main():
    parser = argparse.ArgumentParser(description='SwarmOS bounded workflow demonstrator')
    parser.add_argument('command', choices=['demo', 'inspect', 'list', 'export', 'verify', 'recover', 'timeline', 'evaluate', 'memory-clear', 'mcp'])
    parser.add_argument('--output', default='evidence/demo')
    parser.add_argument('--database', default='.swarmos/runs.sqlite3')
    parser.add_argument('--run-id')
    parser.add_argument('--project', default=str(Path.cwd().resolve()))
    parser.add_argument('--memory', choices=['on', 'off'], default='off')
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--proposal')
    parser.add_argument('--approve-proposal', help='SHA-256 of the exact proposal bytes you reviewed')
    args = parser.parse_args()
    if args.command in {'inspect', 'export', 'verify', 'recover', 'timeline'} and not args.run_id:
        parser.error('--run-id is required')
    try:
        if args.command == 'mcp':
            from .mcp_server import serve
            serve(args.database, args.project)
            return 0
        if args.command == 'evaluate':
            from .evaluation import evaluate
            path, report = evaluate(args.output, args.trials)
            print(json.dumps(report['summary'], indent=2))
            print(f'Report: {path}')
            return 0 if all(row['successes'] == args.trials for row in report['summary'].values()) else 1
        with RunHistory(args.database) as history:
            if args.command == 'demo':
                from .execution import execute
                operations = None
                digest = None
                if args.proposal:
                    from .proposals import load_proposal
                    operations, digest = load_proposal(args.proposal, args.approve_proposal)
                data = execute(history, args.output, args.project, args.memory == 'on', operations, digest)
                print(f"Run ID: {data['run_id']}\nTermination: {data['termination']}\nMemory hit: {data['memory_hit']}")
                print(f"Timeline: {Path(args.output) / data['run_id'] / 'timeline.html'}")
                return 0 if data['completed'] else 1
            if args.command == 'memory-clear':
                from .memory import Memory
                Memory(history, args.project).clear()
                print('Project memory cleared.')
            elif args.command == 'timeline':
                from .timeline import render
                print(render(history, args.run_id, args.output))
            elif args.command == 'recover':
                run, _, _ = history.get(args.run_id)
                result = ControllerResult(TerminationCode.OPERATION_FAILED, (), 0,
                                          'operator marked interrupted run failed; partial execution unknown')
                history.finish(run, result, evidence.payload(run, result))
                print('Marked failed. Export evidence with the export command.')
            elif args.command == 'export':
                print(evidence.export(history, args.run_id, args.output))
            elif args.command == 'verify':
                evidence.verify(history, args.run_id, args.output)
                print('Evidence matches durable run payload.')
            elif args.command == 'inspect':
                run, tasks, events = history.get(args.run_id)
                print(f'Run: {run.id}\nStatus: {run.status}\nStarted: {run.started_at}\nFinished: {run.finished_at}')
                for event in events:
                    if event.kind != 'evidence':
                        print(f'{event.created_at} {event.kind}: {event.payload}')
            else:
                for run in history.recent():
                    print(f'{run.id} {run.status} {run.started_at}')
        return 0
    except Exception as error:
        print(f'{type(error).__name__}: {error}. If execution was persisted, retry export with its run ID.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
