"""SQLite persistence for SwarmOS.

SQLite has no user-created schemas, so the application namespace is represented
by the ``swarmos_`` table prefix. Migrations and application data deliberately
share one connection and one database target.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Iterable
from uuid import uuid4


SCHEMA = "swarmos"
TABLE_PREFIX = "swarmos_"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid4())


@dataclass(frozen=True)
class Workflow:
    id: str
    name: str
    description: str | None
    created_at: str


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    role: str
    created_at: str


@dataclass(frozen=True)
class Run:
    id: str
    workflow_id: str
    status: str
    started_at: str
    finished_at: str | None


@dataclass(frozen=True)
class Task:
    id: str
    run_id: str
    agent_id: str | None
    name: str
    status: str
    position: int
    created_at: str


@dataclass(frozen=True)
class Event:
    id: str
    run_id: str
    kind: str
    payload: str
    created_at: str


INITIAL_MIGRATION = (
    1,
    "initial_persistence",
    """
    CREATE TABLE swarmos_workflows (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE swarmos_agents (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        role TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE swarmos_runs (
        id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL REFERENCES swarmos_workflows(id),
        status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
        started_at TEXT NOT NULL,
        finished_at TEXT
    );

    CREATE TABLE swarmos_tasks (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES swarmos_runs(id) ON DELETE CASCADE,
        agent_id TEXT REFERENCES swarmos_agents(id),
        name TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
        position INTEGER NOT NULL CHECK (position >= 0),
        created_at TEXT NOT NULL,
        UNIQUE (run_id, position)
    );

    CREATE TABLE swarmos_events (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES swarmos_runs(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """,
)

MIGRATIONS = (INITIAL_MIGRATION,)
REQUIRED_TABLES = {
    "swarmos_workflows",
    "swarmos_agents",
    "swarmos_runs",
    "swarmos_tasks",
    "swarmos_events",
    "swarmos_schema_migrations",
    "swarmos_migration_lock",
}


class Database:
    """Own the sole application database target and its connection."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self.connection = sqlite3.connect(self.path, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA busy_timeout = 5000")

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    def migrate(self) -> None:
        """Apply every pending migration atomically on this database only."""
        connection = self.connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS swarmos_schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS swarmos_migration_lock (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    acquired_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO swarmos_migration_lock(id, acquired_at) VALUES (1, ?)",
                (_now(),),
            )
            applied = {
                row[0]
                for row in connection.execute(
                    "SELECT version FROM swarmos_schema_migrations"
                )
            }
            for version, name, sql in MIGRATIONS:
                if version in applied:
                    continue
                for statement in sql.split(";"):
                    statement = statement.strip()
                    if statement:
                        connection.execute(statement)
                connection.execute(
                    "INSERT INTO swarmos_schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, _now()),
                )
            actual_tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            missing_tables = REQUIRED_TABLES - actual_tables
            if missing_tables:
                raise RuntimeError(
                    "migration completed without required tables: "
                    + ", ".join(sorted(missing_tables))
                )
            connection.execute(
                "DELETE FROM swarmos_migration_lock WHERE id = 1")
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

    def _execute(self, sql: str, parameters: Iterable[Any] = ()) -> sqlite3.Cursor:
        return self.connection.execute(sql, tuple(parameters))


class WorkflowRepository:
    def __init__(self, database: Database):
        self.database = database

    def create(self, name: str, description: str | None = None) -> Workflow:
        item = Workflow(_new_id(), name, description, _now())
        self.database._execute(
            "INSERT INTO swarmos_workflows(id, name, description, created_at) VALUES (?, ?, ?, ?)",
            (item.id, item.name, item.description, item.created_at),
        )
        return item

    def get(self, workflow_id: str) -> Workflow | None:
        row = self.database._execute(
            "SELECT id, name, description, created_at FROM swarmos_workflows WHERE id = ?",
            (workflow_id,),
        ).fetchone()
        return Workflow(**dict(row)) if row else None

    def get_by_name(self, name: str) -> Workflow | None:
        row = self.database._execute(
            "SELECT id, name, description, created_at FROM swarmos_workflows WHERE name = ?",
            (name,),
        ).fetchone()
        return Workflow(**dict(row)) if row else None


class AgentRepository:
    def __init__(self, database: Database):
        self.database = database

    def create(self, name: str, role: str) -> Agent:
        item = Agent(_new_id(), name, role, _now())
        self.database._execute(
            "INSERT INTO swarmos_agents(id, name, role, created_at) VALUES (?, ?, ?, ?)",
            (item.id, item.name, item.role, item.created_at),
        )
        return item


class RunRepository:
    def __init__(self, database: Database):
        self.database = database

    def create(self, workflow_id: str, status: str = "queued") -> Run:
        item = Run(_new_id(), workflow_id, status, _now(), None)
        self.database._execute(
            "INSERT INTO swarmos_runs(id, workflow_id, status, started_at, finished_at) VALUES (?, ?, ?, ?, ?)",
            (item.id, item.workflow_id, item.status,
             item.started_at, item.finished_at),
        )
        return item

    def get(self, run_id: str) -> Run | None:
        row = self.database._execute(
            "SELECT id, workflow_id, status, started_at, finished_at "
            "FROM swarmos_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        return Run(**dict(row)) if row else None

    def finish(self, run_id: str, status: str) -> None:
        self.database._execute(
            "UPDATE swarmos_runs SET status = ?, finished_at = ? WHERE id = ?",
            (status, _now(), run_id),
        )

    def recent(self, limit: int = 10) -> list[Run]:
        rows = self.database._execute(
            "SELECT id, workflow_id, status, started_at, finished_at "
            "FROM swarmos_runs ORDER BY rowid DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [Run(**dict(row)) for row in rows]

    def add_task(
        self,
        run_id: str,
        name: str,
        position: int,
        agent_id: str | None = None,
        status: str = "queued",
    ) -> Task:
        item = Task(_new_id(), run_id, agent_id,
                    name, status, position, _now())
        self.database._execute(
            "INSERT INTO swarmos_tasks(id, run_id, agent_id, name, status, position, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (item.id, item.run_id, item.agent_id, item.name,
             item.status, item.position, item.created_at),
        )
        return item

    def add_event(self, run_id: str, kind: str, payload: str) -> Event:
        item = Event(_new_id(), run_id, kind, payload, _now())
        self.database._execute(
            "INSERT INTO swarmos_events(id, run_id, kind, payload, created_at) VALUES (?, ?, ?, ?, ?)",
            (item.id, item.run_id, item.kind, item.payload, item.created_at),
        )
        return item

    def tasks(self, run_id: str) -> list[Task]:
        rows = self.database._execute(
            "SELECT id, run_id, agent_id, name, status, position, created_at FROM swarmos_tasks WHERE run_id = ? ORDER BY position",
            (run_id,),
        ).fetchall()
        return [Task(**dict(row)) for row in rows]

    def events(self, run_id: str) -> list[Event]:
        rows = self.database._execute(
            "SELECT id, run_id, kind, payload, created_at FROM swarmos_events WHERE run_id = ? ORDER BY rowid",
            (run_id,),
        ).fetchall()
        return [Event(**dict(row)) for row in rows]
