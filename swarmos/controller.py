"""Deterministic, bounded controller for the Phase 1 coding workflow."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePath
import os
from pathlib import Path
import hashlib
import re
import subprocess
import sys
from typing import Any, Mapping


class Role(StrEnum):
    PLANNER = "planner"
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"


class TerminationCode(StrEnum):
    COMPLETED = "completed"
    UNAUTHORIZED_TOOL = "unauthorized_tool"
    OUT_OF_SCOPE_OPERATION = "out_of_scope_operation"
    PATCH_LIMIT_EXCEEDED = "patch_limit_exceeded"
    STEP_LIMIT_EXCEEDED = "step_limit_exceeded"
    OPERATION_FAILED = "operation_failed"
    ACCEPTANCE_FAILED = "acceptance_failed"
    INCOMPLETE_WORKFLOW = "incomplete_workflow"


ROLE_TOOL_ALLOWLIST: dict[Role, frozenset[str]] = {
    Role.PLANNER: frozenset({"inspect_workspace", "propose_plan"}),
    Role.IMPLEMENTER: frozenset({"apply_patch"}),
    Role.REVIEWER: frozenset({"inspect_workspace", "git_diff", "run_tests"}),
}

_ROLE_ORDER = (Role.PLANNER, Role.IMPLEMENTER, Role.REVIEWER)
_FIXTURE_MARKER = ".swarmos-phase1-fixture"
_ACCEPTANCE_SHA256 = "6FB9D0D6D029A0EBA36F01FF9FBA30AE9CA2D3BA0ABEA31B2DB510C0BDF279E7"
_EXPECTED_ACCEPTANCE_TESTS = 1
_OWNED_FIXTURES: set[Path] = set()


@dataclass(frozen=True)
class Operation:
    role: Role
    tool: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Step:
    number: int
    role: Role
    tool: str
    result: str


@dataclass(frozen=True)
class ControllerResult:
    termination: TerminationCode
    steps: tuple[Step, ...]
    patches_attempted: int
    message: str
    diff: str = ""

    @property
    def completed(self) -> bool:
        return self.termination is TerminationCode.COMPLETED


class BoundedController:
    """Execute only explicitly supported, deterministic workflow operations."""

    MAX_STEPS = 8
    MAX_PATCH_ATTEMPTS = 1

    def __init__(
        self,
        fixture_root: Path | None = None,
        acceptance_test: Path | None = None,
    ) -> None:
        self._steps: list[Step] = []
        self._patches_attempted = 0
        self._fixture_root = fixture_root
        self._acceptance_test = acceptance_test
        self._diff = ""
        self._patch_applied = False
        self._diff_verified = False
        self._acceptance_passed = False
        self._diagnostic = ""

    def run(self, operations: list[Operation] | tuple[Operation, ...]) -> ControllerResult:
        self._steps = []
        self._patches_attempted = 0
        self._diff = ""
        self._patch_applied = False
        self._diff_verified = False
        self._acceptance_passed = False
        self._diagnostic = ""
        expected = (
            (Role.PLANNER, "inspect_workspace"),
            (Role.PLANNER, "propose_plan"),
            (Role.IMPLEMENTER, "apply_patch"),
            (Role.REVIEWER, "git_diff"),
            (Role.REVIEWER, "run_tests"),
        )
        last_role_index = -1

        for operation in operations:
            if len(self._steps) >= self.MAX_STEPS:
                return self._terminate(
                    TerminationCode.STEP_LIMIT_EXCEEDED,
                    "maximum step count reached before the next operation",
                )

            if operation.role not in ROLE_TOOL_ALLOWLIST or (
                operation.tool not in ROLE_TOOL_ALLOWLIST[operation.role]
            ):
                return self._terminate(
                    TerminationCode.UNAUTHORIZED_TOOL,
                    f"{operation.role.value} cannot call {operation.tool}",
                )

            role_index = _ROLE_ORDER.index(operation.role)
            if role_index < last_role_index:
                return self._terminate(
                    TerminationCode.OUT_OF_SCOPE_OPERATION,
                    "workflow roles are reordered",
                )
            last_role_index = role_index

            outcome = self._execute(operation)
            if isinstance(outcome, TerminationCode):
                return self._terminate(outcome, self._failure_message(outcome))

            self._steps.append(
                Step(len(self._steps) + 1, operation.role, operation.tool, outcome)
            )

        if (
            [(step.role, step.tool) for step in self._steps] != list(expected)
            or not self._patch_applied
            or not self._diff_verified
            or not self._acceptance_passed
        ):
            return self._terminate(
                TerminationCode.INCOMPLETE_WORKFLOW,
                "approval requires an applied patch, verified diff, and passing acceptance",
            )

        return ControllerResult(
            TerminationCode.COMPLETED,
            tuple(self._steps),
            self._patches_attempted,
            "bounded sequence completed",
            self._diff,
        )

    def _execute(self, operation: Operation) -> str | TerminationCode:
        arguments = operation.arguments
        if operation.tool == "inspect_workspace":
            path = arguments.get("path", ".")
            if not isinstance(path, str) or not self._is_safe_relative_path(path):
                return TerminationCode.OUT_OF_SCOPE_OPERATION
            return f"inspected:{path}"

        if operation.tool == "propose_plan":
            plan = arguments.get("plan")
            if not isinstance(plan, str) or not plan.strip():
                return TerminationCode.OPERATION_FAILED
            return "plan:bounded-coding-sequence"

        if operation.tool == "apply_patch":
            if self._patches_attempted >= self.MAX_PATCH_ATTEMPTS:
                return TerminationCode.PATCH_LIMIT_EXCEEDED
            self._patches_attempted += 1
            files = arguments.get("files")
            if (
                not isinstance(files, list)
                or not files
                or any(
                    not isinstance(path, str) or not self._is_safe_relative_path(path)
                    for path in files
                )
            ):
                return TerminationCode.OUT_OF_SCOPE_OPERATION
            if (
                self._fixture_root is None
                or files != ["src/labels.py"]
                or arguments.get("patch") != "swarm001_normalize_label"
            ):
                return TerminationCode.OUT_OF_SCOPE_OPERATION
            target = self._fixture_root / "src" / "labels.py"
            try:
                self._validate_owned_fixture()
                target = self._confined_target(target)
                if not target.is_file():
                    return self._fail(
                        TerminationCode.OPERATION_FAILED,
                        "authorized patch target is missing",
                    )
                target.write_text(
                    '"""Deterministic SWARM-001 fixture implementation."""\n\n'
                    "def normalize_label(text: str) -> str:\n"
                    "    normalized = text.strip()\n"
                    "    if not normalized:\n"
                    '        raise ValueError("label must not be empty")\n'
                    '    ascii_lower = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")\n'
                    '    return "-".join(normalized.translate(ascii_lower).split())\n',
                    encoding="utf-8",
                )
            except (OSError, ValueError) as error:
                return self._fail(
                    TerminationCode.OPERATION_FAILED,
                    f"patch filesystem failure: {error}",
                )
            self._patch_applied = True
            return f"patch-attempted:{len(files)}-file(s)"

        if operation.tool == "git_diff":
            if self._fixture_root is None or not self._patch_applied:
                return self._fail(
                    TerminationCode.ACCEPTANCE_FAILED,
                    "diff verification requires a successfully applied patch",
                )
            try:
                diff = _run_git(self._fixture_root, "diff", "--", "src/labels.py")
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                return self._fail(
                    TerminationCode.OPERATION_FAILED,
                    f"git diff failure: {error}",
                )
            if (
                not diff
                or "src/labels.py" not in diff
                or "def normalize_label(text: str) -> str:" not in diff
            ):
                return self._fail(
                    TerminationCode.ACCEPTANCE_FAILED,
                    "authorized non-empty SWARM-001 diff was not verified",
                )
            self._diff = diff
            self._diff_verified = True
            return "git-diff:present"

        if operation.tool == "run_tests":
            if arguments.get("command") != "swarm001_acceptance":
                return TerminationCode.OUT_OF_SCOPE_OPERATION
            if not self._diff_verified:
                return self._fail(
                    TerminationCode.ACCEPTANCE_FAILED,
                    "acceptance requires a verified Git diff",
                )
            try:
                acceptance = self._trusted_acceptance_test()
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "-q",
                        str(acceptance),
                    ],
                    cwd=acceptance.parent.parent,
                    env={
                        **os.environ,
                        "SWARM001_FIXTURE_ROOT": str(self._fixture_root),
                    },
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
                return self._fail(
                    TerminationCode.OPERATION_FAILED,
                    f"acceptance subprocess failure: {error}",
                )
            if completed.returncode != 0:
                return self._fail(
                    TerminationCode.ACCEPTANCE_FAILED,
                    f"acceptance failed: {completed.stdout[-500:]} {completed.stderr[-500:]}",
                )
            summary = completed.stdout + completed.stderr
            passed = re.search(r"(?m)(\d+) passed\b", summary)
            skipped = re.search(r"(?m)(\d+) skipped\b", summary)
            if (
                passed is None
                or int(passed.group(1)) != _EXPECTED_ACCEPTANCE_TESTS
                or (skipped is not None and int(skipped.group(1)) > 0)
            ):
                return self._fail(
                    TerminationCode.ACCEPTANCE_FAILED,
                    "acceptance evidence did not report exactly one passed and zero skipped tests",
                )
            self._acceptance_passed = True
            return f"acceptance:passed={passed.group(1)};skipped=0"

        return TerminationCode.UNAUTHORIZED_TOOL

    @staticmethod
    def _is_safe_relative_path(path: str) -> bool:
        candidate = PurePath(path)
        return (
            path not in {"", "."}
            and not candidate.is_absolute()
            and ".." not in candidate.parts
        ) or path == "."

    @staticmethod
    def _failure_message(code: TerminationCode) -> str:
        return {
            TerminationCode.OUT_OF_SCOPE_OPERATION: "operation is outside the controller scope",
            TerminationCode.PATCH_LIMIT_EXCEEDED: "maximum patch attempts exceeded",
            TerminationCode.STEP_LIMIT_EXCEEDED: "maximum step count exceeded",
            TerminationCode.OPERATION_FAILED: "operation failed validation",
            TerminationCode.ACCEPTANCE_FAILED: "acceptance evidence missing or failed",
            TerminationCode.INCOMPLETE_WORKFLOW: "workflow did not reach all approval gates",
            TerminationCode.UNAUTHORIZED_TOOL: "tool call is not authorized",
        }.get(code, "controller terminated")

    def _fail(self, code: TerminationCode, diagnostic: str) -> TerminationCode:
        self._diagnostic = diagnostic
        return code

    def _confined_target(self, target: Path) -> Path:
        if self._fixture_root is None:
            raise ValueError("fixture root is not configured")
        root = self._canonical_fixture_root()
        if target.is_symlink() or (root / "src").is_symlink():
            raise ValueError("symlinked patch path is not allowed")
        resolved = target.resolve(strict=False)
        if resolved != root / "src" / "labels.py":
            raise ValueError("patch target resolves outside fixture")
        if target.parent.resolve(strict=True) != root / "src":
            raise ValueError("patch parent resolves outside fixture")
        return target

    def _canonical_fixture_root(self) -> Path:
        if self._fixture_root is None:
            raise ValueError("fixture root is not configured")
        root = self._fixture_root
        if root.is_symlink():
            raise ValueError("symlinked fixture root is not allowed")
        resolved = root.resolve(strict=True)
        if (
            not resolved.is_dir()
            or not (resolved / ".git").is_dir()
            or not (resolved / _FIXTURE_MARKER).is_file()
            or resolved not in _OWNED_FIXTURES
        ):
            raise ValueError("fixture root is not a controller-owned disposable repository")
        return resolved

    def _validate_owned_fixture(self) -> None:
        self._canonical_fixture_root()

    def _trusted_acceptance_test(self) -> Path:
        expected = (Path(__file__).parent.parent / "tests" / "test_swarm001_acceptance.py").resolve(
            strict=True
        )
        if self._acceptance_test is None:
            raise ValueError("acceptance test is not configured")
        if self._acceptance_test.is_symlink():
            raise ValueError("symlinked acceptance test is not allowed")
        candidate = self._acceptance_test.resolve(strict=True)
        if candidate != expected:
            raise ValueError("acceptance test is not the trusted project test")
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest().upper()
        if digest != _ACCEPTANCE_SHA256:
            raise ValueError("acceptance test integrity check failed")
        return expected

    def _terminate(
        self, termination: TerminationCode, message: str
    ) -> ControllerResult:
        return ControllerResult(
            termination,
            tuple(self._steps),
            self._patches_attempted,
            f"{message}; {self._diagnostic}" if self._diagnostic else message,
            self._diff,
        )


def demo_operations() -> tuple[Operation, ...]:
    """Return the deterministic sequence used by the CLI evidence demo."""
    return (
        Operation(Role.PLANNER, "inspect_workspace", {"path": "."}),
        Operation(
            Role.PLANNER,
            "propose_plan",
            {"plan": "inspect, apply normalize_label patch, then review"},
        ),
        Operation(
            Role.IMPLEMENTER,
            "apply_patch",
            {"files": ["src/labels.py"], "patch": "swarm001_normalize_label"},
        ),
        Operation(Role.REVIEWER, "git_diff"),
        Operation(Role.REVIEWER, "run_tests", {"command": "swarm001_acceptance"}),
    )


def _run_git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout


def create_swarm001_fixture(root: Path) -> None:
    """Create and baseline the disposable, deterministic SWARM-001 repository."""
    if root.exists():
        raise ValueError("fixture root must be freshly created and unused")
    root.mkdir(parents=True)
    source = root / "src" / "labels.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        '"""SWARM-001 disposable fixture."""\n\n'
        "def normalize_label(text: str) -> str:\n"
        "    return text.strip()\n",
        encoding="utf-8",
    )
    _run_git(root, "init", "-q")
    _run_git(root, "config", "user.name", "SwarmOS Fixture")
    _run_git(root, "config", "user.email", "fixture@swarmos.invalid")
    _run_git(root, "add", "--", "src/labels.py")
    _run_git(root, "commit", "-q", "-m", "baseline SWARM-001 fixture")
    (root / _FIXTURE_MARKER).write_text(
        "SwarmOS Phase 1 controller-owned disposable fixture\n",
        encoding="utf-8",
    )
    _run_git(root, "add", "--", _FIXTURE_MARKER)
    _run_git(root, "commit", "-q", "-m", "mark controller-owned fixture")
    _OWNED_FIXTURES.add(root.resolve())


def run_swarm001(root: Path, acceptance_test: Path) -> ControllerResult:
    try:
        create_swarm001_fixture(root)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        return ControllerResult(
            TerminationCode.OPERATION_FAILED,
            (),
            0,
            f"fixture initialization failure: {error}",
        )
    return BoundedController(root, acceptance_test).run(
        (
            Operation(Role.PLANNER, "inspect_workspace", {"path": "."}),
            Operation(Role.PLANNER, "propose_plan", {"plan": "implement SWARM-001"}),
            Operation(
                Role.IMPLEMENTER,
                "apply_patch",
                {"files": ["src/labels.py"], "patch": "swarm001_normalize_label"},
            ),
            Operation(Role.REVIEWER, "git_diff"),
            Operation(Role.REVIEWER, "run_tests", {"command": "swarm001_acceptance"}),
        )
    )
