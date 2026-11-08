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
    parser.add_argument('command', choices=['demo', 'inspect', 'list', 'export', 'verify', 'recover'])
    parser.add_argument('--output', default='evidence/demo')
    parser.add_argument('--database', default='.swarmos/runs.sqlite3')
    parser.add_argument('--run-id')
    args = parser.parse_args()
    if args.command in {'inspect', 'export', 'verify', 'recover'} and not args.run_id:
        parser.error('--run-id is required')
    try:
        with RunHistory(args.database) as history:
            if args.command == 'demo':
                run = history.start()
                print(f'Run ID: {run.id}', flush=True)
                try:
                    result = run_swarm001(
                        Path(args.output).resolve() / run.id / 'fixture',
                        Path(__file__).parent.parent / 'tests' / 'test_swarm001_acceptance.py')
                except Exception as error:
                    result = ControllerResult(TerminationCode.OPERATION_FAILED, (), 0,
                                              f'unexpected execution failure: {type(error).__name__}: {error}')
                history.finish(run, result, evidence.payload(run, result))
                root = evidence.export(history, run.id, args.output)
                print(f'Termination: {result.termination.value}\nEvidence: {root}')
                return 0 if result.completed else 1
            if args.command == 'recover':
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
