import sqlite3

import pytest

import swarmos.persistence as persistence
from swarmos.persistence import AgentRepository, Database, RunRepository, WorkflowRepository


def test_migrations_are_idempotent_and_keep_app_tables_namespaced(tmp_path):
    path = tmp_path / "app.sqlite3"
    with Database(path) as database:
        database.migrate()
        database.migrate()

        tables = {
            row[0]
            for row in database.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "swarmos_schema_migrations" in tables
        assert "swarmos_migration_lock" in tables
        assert all(name.startswith("swarmos_") for name in tables)
        assert database.connection.execute(
            "SELECT COUNT(*) FROM swarmos_schema_migrations"
        ).fetchone()[0] == 1
        assert database.connection.execute(
            "SELECT COUNT(*) FROM swarmos_migration_lock"
        ).fetchone()[0] == 0


def test_failed_migration_rolls_back_history_and_schema(tmp_path, monkeypatch):
    path = tmp_path / "failed.sqlite3"
    monkeypatch.setattr(
        persistence,
        "MIGRATIONS",
        ((1, "broken", "CREATE TABLE swarmos_workflows (id TEXT); NOT SQL;"),),
    )
    with Database(path) as database:
        with pytest.raises(sqlite3.OperationalError, match="near \"NOT\""):
            database.migrate()

    connection = sqlite3.connect(path)
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert "swarmos_schema_migrations" not in tables
    assert "swarmos_workflows" not in tables
    connection.close()


def test_repositories_use_foreign_keys_and_preserve_order(tmp_path):
    with Database(tmp_path / "repositories.sqlite3") as database:
        database.migrate()
        workflow = WorkflowRepository(
            database).create("release", "Ship the run")
        agent = AgentRepository(database).create("builder", "implementation")
        run = RunRepository(database).create(workflow.id)
        runs = RunRepository(database)
        runs.add_task(run.id, "second", 1, agent.id)
        runs.add_task(run.id, "first", 0, agent.id)
        runs.add_event(run.id, "started", '{"source":"test"}')

        assert [task.name for task in runs.tasks(run.id)] == [
            "first", "second"]
        assert runs.events(run.id)[0].kind == "started"
        with pytest.raises(sqlite3.IntegrityError):
            runs.create("missing-workflow")
