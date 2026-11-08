from pathlib import Path
import sys

import pytest

from swarmos.controller import (
    BoundedController,
    Operation,
    Role,
    TerminationCode,
    create_swarm001_fixture,
    run_swarm001,
)


def _valid_operations():
    return [
        Operation(Role.PLANNER, "inspect_workspace", {"path": "."}),
        Operation(Role.PLANNER, "propose_plan", {
                  "plan": "implement SWARM-001"}),
        Operation(
            Role.IMPLEMENTER,
            "apply_patch",
            {"files": ["src/labels.py"], "patch": "swarm001_normalize_label"},
        ),
        Operation(Role.REVIEWER, "git_diff"),
        Operation(Role.REVIEWER, "run_tests", {
                  "command": "swarm001_acceptance"}),
    ]


def test_swarm001_runs_authorized_bounded_sequence(tmp_path):
    fixture = tmp_path / "fixture"
    acceptance = Path(__file__).with_name(
        "test_swarm001_acceptance.py"
    )
    result = run_swarm001(fixture, acceptance)

    assert result.termination is TerminationCode.COMPLETED
    assert [step.tool for step in result.steps] == [
        "inspect_workspace",
        "propose_plan",
        "apply_patch",
        "git_diff",
        "run_tests",
    ]
    assert result.patches_attempted == 1
    assert "def normalize_label(text: str) -> str:" in result.diff


def test_unauthorized_role_tool_terminates_without_continuing():
    result = BoundedController().run(
        [Operation(Role.PLANNER, "apply_patch", {"files": ["x.txt"]})]
    )

    assert result.termination is TerminationCode.UNAUTHORIZED_TOOL
    assert not result.steps


def test_second_patch_attempt_terminates(tmp_path):
    fixture = tmp_path / "fixture"
    create_swarm001_fixture(fixture)
    result = BoundedController(fixture).run(
        [
            Operation(
                Role.IMPLEMENTER,
                "apply_patch",
                {"files": ["src/labels.py"],
                    "patch": "swarm001_normalize_label"},
            ),
            Operation(
                Role.IMPLEMENTER,
                "apply_patch",
                {"files": ["src/labels.py"],
                    "patch": "swarm001_normalize_label"},
            ),
        ]
    )

    assert result.termination is TerminationCode.PATCH_LIMIT_EXCEEDED
    assert len(result.steps) == 1
    assert result.patches_attempted == 1


def test_out_of_scope_fixture_write_is_rejected(tmp_path):
    fixture = tmp_path / "fixture"
    create_swarm001_fixture(fixture)
    result = BoundedController(fixture).run(
        [
            Operation(
                Role.IMPLEMENTER,
                "apply_patch",
                {"files": ["README.md"], "patch": "swarm001_normalize_label"},
            )
        ]
    )

    assert result.termination is TerminationCode.OUT_OF_SCOPE_OPERATION
    assert not (fixture / "README.md").exists()


def test_reviewer_rejects_false_approval_without_diff_or_acceptance(tmp_path):
    fixture = tmp_path / "fixture"
    create_swarm001_fixture(fixture)
    acceptance = Path(__file__).with_name("test_swarm001_acceptance.py")
    result = BoundedController(fixture, acceptance).run(
        [Operation(Role.REVIEWER, "git_diff")]
    )

    assert result.termination is TerminationCode.ACCEPTANCE_FAILED
    assert not result.completed


@pytest.mark.parametrize(
    "operations",
    [
        [],
        [Operation(Role.PLANNER, "inspect_workspace", {"path": "."})],
        [Operation(Role.REVIEWER, "inspect_workspace", {"path": "."})],
        [Operation(Role.REVIEWER, "git_diff")],
        [Operation(Role.REVIEWER, "run_tests", {
                   "command": "swarm001_acceptance"})],
    ],
)
def test_incomplete_workflows_never_approve(tmp_path, operations):
    fixture = tmp_path / "fixture"
    create_swarm001_fixture(fixture)
    acceptance = Path(__file__).with_name("test_swarm001_acceptance.py")

    result = BoundedController(fixture, acceptance).run(operations)

    assert not result.completed
    assert result.termination is not TerminationCode.COMPLETED


def test_reordered_and_duplicated_workflows_never_approve(tmp_path):
    fixture = tmp_path / "fixture"
    create_swarm001_fixture(fixture)
    operations = _valid_operations()
    operations.insert(1, operations[0])

    result = BoundedController(
        fixture, Path(__file__).with_name("test_swarm001_acceptance.py")
    ).run(operations)

    assert not result.completed
    assert result.termination is TerminationCode.INCOMPLETE_WORKFLOW


def test_failed_acceptance_never_approves(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture"
    create_swarm001_fixture(fixture)
    real_run = __import__("swarmos.controller", fromlist=[
                          "subprocess"]).subprocess.run

    def failed_acceptance(command, **kwargs):
        if command[0] == sys.executable and command[1:3] == ["-m", "pytest"]:
            return __import__("subprocess").CompletedProcess(
                command, 1, stdout="failed acceptance", stderr=""
            )
        return real_run(command, **kwargs)

    monkeypatch.setattr("swarmos.controller.subprocess.run", failed_acceptance)
    result = BoundedController(
        fixture, Path(__file__).with_name("test_swarm001_acceptance.py")
    ).run(_valid_operations())

    assert result.termination is TerminationCode.ACCEPTANCE_FAILED
    assert not result.completed


def test_untrusted_acceptance_path_never_approves(tmp_path):
    fixture = tmp_path / "fixture"
    create_swarm001_fixture(fixture)
    untrusted = tmp_path / "acceptance.py"
    untrusted.write_text("def test_fake(): pass\n", encoding="utf-8")

    result = BoundedController(fixture, untrusted).run(_valid_operations())

    assert result.termination is TerminationCode.OPERATION_FAILED
    assert not result.completed


def test_existing_git_repository_is_not_accepted_as_fixture(tmp_path):
    fixture = tmp_path / "existing"
    create_swarm001_fixture(fixture)
    with pytest.raises(ValueError, match="freshly created"):
        create_swarm001_fixture(fixture)


def test_run_swarm001_converts_existing_root_failure(tmp_path):
    fixture = tmp_path / "existing"
    create_swarm001_fixture(fixture)

    result = run_swarm001(
        fixture, Path(__file__).with_name("test_swarm001_acceptance.py")
    )

    assert result.termination is TerminationCode.OPERATION_FAILED
    assert not result.completed


def test_unowned_git_repository_never_approves(tmp_path):
    fixture = tmp_path / "repo"
    fixture.mkdir()
    __import__("subprocess").run(
        ["git", "init", "-q"], cwd=fixture, check=True)
    result = BoundedController(fixture).run(_valid_operations())

    assert result.termination is TerminationCode.OPERATION_FAILED
    assert not result.completed


def test_acceptance_integrity_mismatch_never_approves(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture"
    create_swarm001_fixture(fixture)
    monkeypatch.setattr("swarmos.controller._ACCEPTANCE_SHA256", "0" * 64)

    result = BoundedController(
        fixture, Path(__file__).with_name("test_swarm001_acceptance.py")
    ).run(_valid_operations())

    assert result.termination is TerminationCode.OPERATION_FAILED
    assert "integrity" in result.message
    assert not result.completed


def test_acceptance_evidence_must_report_expected_count(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture"
    create_swarm001_fixture(fixture)
    real_run = __import__("swarmos.controller", fromlist=[
                          "subprocess"]).subprocess.run

    def missing_evidence(command, **kwargs):
        if command[0] == sys.executable and command[1:3] == ["-m", "pytest"]:
            return __import__("subprocess").CompletedProcess(
                command, 0, stdout="no tests ran\n", stderr=""
            )
        return real_run(command, **kwargs)

    monkeypatch.setattr("swarmos.controller.subprocess.run", missing_evidence)
    result = BoundedController(
        fixture, Path(__file__).with_name("test_swarm001_acceptance.py")
    ).run(_valid_operations())

    assert result.termination is TerminationCode.ACCEPTANCE_FAILED
    assert not result.completed


def test_git_subprocess_failure_never_approves(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture"
    create_swarm001_fixture(fixture)
    monkeypatch.setattr(
        "swarmos.controller._run_git",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("git unavailable")),
    )

    result = BoundedController(fixture).run(_valid_operations()[:4])

    assert result.termination is TerminationCode.OPERATION_FAILED
    assert "git diff failure" in result.message
    assert not result.completed


def test_symlink_redirection_is_rejected(tmp_path):
    fixture = tmp_path / "fixture"
    external = tmp_path / "external.py"
    create_swarm001_fixture(fixture)
    external.write_text("external", encoding="utf-8")
    target = fixture / "src" / "labels.py"
    target.unlink()
    try:
        target.symlink_to(external)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    result = BoundedController(fixture).run(
        [
            Operation(
                Role.IMPLEMENTER,
                "apply_patch",
                {"files": ["src/labels.py"],
                    "patch": "swarm001_normalize_label"},
            )
        ]
    )

    assert result.termination is TerminationCode.OPERATION_FAILED
    assert external.read_text(encoding="utf-8") == "external"


def test_step_limit_terminates_before_ninth_operation():
    operations = [
        Operation(Role.REVIEWER, "inspect_workspace", {"path": "."})
        for _ in range(9)
    ]

    result = BoundedController().run(operations)

    assert result.termination is TerminationCode.STEP_LIMIT_EXCEEDED
    assert len(result.steps) == 8


def test_out_of_scope_path_terminates():
    result = BoundedController().run(
        [Operation(Role.PLANNER, "inspect_workspace", {"path": "../secrets"})]
    )

    assert result.termination is TerminationCode.OUT_OF_SCOPE_OPERATION
    assert not result.steps


def test_failed_operation_terminates_without_silent_continuation():
    result = BoundedController().run(
        [
            Operation(Role.PLANNER, "propose_plan", {"plan": ""}),
            Operation(Role.PLANNER, "inspect_workspace", {"path": "."}),
        ]
    )

    assert result.termination is TerminationCode.OPERATION_FAILED
    assert not result.steps
