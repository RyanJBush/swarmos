import json

import pytest

from swarmos.controller import ControllerResult, Role, Step, TerminationCode
from swarmos.run_history import RunHistory


def _result(completed=True):
    return ControllerResult(
        TerminationCode.COMPLETED if completed else TerminationCode.OPERATION_FAILED,
        (
            Step(1, Role.PLANNER, "inspect_workspace", "inspected:."),
            Step(2, Role.IMPLEMENTER, "apply_patch", "patch-attempted:1-file(s)"),
        ),
        1,
        "ok" if completed else "failure detail",
    )


def test_successful_run_persists_steps_and_recovers_after_restart(tmp_path):
    path = tmp_path / "runs.sqlite3"
    with RunHistory(path) as history:
        run = history.start()
        history.finish(run, _result())
        run_id = run.id

    with RunHistory(path) as history:
        recovered, tasks, events = history.get(run_id)
        assert recovered.status == "succeeded"
        assert [task.position for task in tasks] == [0, 1]
        assert json.loads(events[0].payload)["sequence"] == 1
        assert json.loads(events[-1].payload)["status"] == "succeeded"


def test_failed_run_persists_termination_reason(tmp_path):
    with RunHistory(tmp_path / "runs.sqlite3") as history:
        run = history.start()
        history.finish(run, _result(False))
        recovered, _, events = history.get(run.id)
        assert recovered.status == "failed"
        assert json.loads(events[-1].payload)["termination"] == "operation_failed"
        assert "failure detail" in json.loads(events[-1].payload)["reason"]


def test_missing_run_id_is_predictable(tmp_path):
    with RunHistory(tmp_path / "runs.sqlite3") as history:
        with pytest.raises(KeyError, match="run not found"):
            history.get("missing")


def test_nested_database_parent_is_initialized(tmp_path):
    with RunHistory(tmp_path / "nested" / "runs.sqlite3") as history:
        assert history.recent() == []
