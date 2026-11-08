"""Persistence adapter for bounded workflow executions."""

from __future__ import annotations

import json
from pathlib import Path

from .controller import ControllerResult
from .persistence import (
    AgentRepository,
    Database,
    Run,
    RunRepository,
    WorkflowRepository,
)


WORKFLOW_NAME = "swarm001-normalize-label"


class RunHistory:
    """Store and inspect controller runs using the existing SQLite repositories."""

    def __init__(self, path: str | Path):
        database_path = Path(path)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database = Database(database_path)
        try:
            self.database.migrate()
        except BaseException:
            self.database.close()
            raise
        self.workflows = WorkflowRepository(self.database)
        self.runs = RunRepository(self.database)

    def close(self) -> None:
        self.database.close()

    def __enter__(self) -> "RunHistory":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def start(self) -> Run:
        with self.database.transaction():
            workflow = self.workflows.get_by_name(WORKFLOW_NAME)
            if workflow is None:
                workflow = self.workflows.create(
                    WORKFLOW_NAME,
                    "Deterministic bounded SWARM-001 normalize_label workflow",
                )
            return self.runs.create(workflow.id, "running")

    def finish(self, run: Run, result: ControllerResult, evidence: dict | None = None) -> None:
        with self.database.transaction():
            current = self.runs.get(run.id)
            if current is None or current.status != "running":
                raise ValueError("only an existing running run can be finalized")
            status = "succeeded" if result.completed else "failed"
            agents = AgentRepository(self.database)
            agent_ids = {
                role: agents.create(
                    f"{role}-{run.id}", role
                ).id
                for role in ("planner", "implementer", "reviewer")
            }
            for step in result.steps:
                self.runs.add_task(
                    run.id,
                    step.tool,
                    step.number - 1,
                    agent_ids[step.role.value],
                    "succeeded",
                )
                self.runs.add_event(
                    run.id,
                    "step",
                    json.dumps(
                        {
                            "sequence": step.number,
                            "role": step.role.value,
                            "operation": step.tool,
                            "result": step.result,
                        },
                        sort_keys=True,
                    ),
                )
            for trace in result.traces:
                self.runs.add_event(run.id, "trace", json.dumps(trace, sort_keys=True))
            self.runs.add_event(
                run.id,
                "termination",
                json.dumps(
                    {
                        "status": status,
                        "termination": result.termination.value,
                        "reason": result.message,
                    },
                    sort_keys=True,
                ),
            )
            self.runs.finish(run.id, status)
            if evidence is not None:
                self.runs.add_event(run.id, "evidence", json.dumps(evidence, sort_keys=True))

    def get(self, run_id: str) -> tuple[Run, list, list]:
        run = self.runs.get(run_id)
        if run is None:
            raise KeyError(f"run not found: {run_id}")
        return run, self.runs.tasks(run_id), self.runs.events(run_id)

    def recent(self, limit: int = 10) -> list[Run]:
        return self.runs.recent(limit)
