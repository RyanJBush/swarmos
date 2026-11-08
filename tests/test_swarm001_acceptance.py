import os
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    "SWARM001_FIXTURE_ROOT" not in os.environ,
    reason="acceptance test requires the controller-provided fixture",
)


def test_swarm001_labels_are_present_in_fixture():
    fixture = Path(os.environ["SWARM001_FIXTURE_ROOT"])
    import importlib.util

    module_path = fixture / "src" / "labels.py"
    spec = importlib.util.spec_from_file_location(
        "swarm001_labels", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.normalize_label("  Hello World  ") == "hello-world"
    assert module.normalize_label("BUG_FIX") == "bug_fix"
    assert module.normalize_label(" Multiple   Spaces ") == "multiple-spaces"
    assert module.normalize_label("A\tB\nC") == "a-b-c"
    assert module.normalize_label("ÄBC_123") == "Äbc_123"
    with pytest.raises(ValueError):
        module.normalize_label("   ")
