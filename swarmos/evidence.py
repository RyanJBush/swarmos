"""Durable evidence outbox: SQLite is authoritative; exports are repairable."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import os
from uuid import uuid4


def payload(run, result):
    return {"schema_version": 1, "run_id": run.id, **asdict(result),
            "termination": result.termination.value, "completed": result.completed}


def stored(history, run_id):
    _, _, events = history.get(run_id)
    evidence = [json.loads(e.payload) for e in events if e.kind == "evidence"]
    if len(evidence) != 1:
        raise ValueError("run has no unique durable evidence payload")
    return evidence[0]


def files_for(data):
    return {"run-summary.json": (json.dumps(data, indent=2, sort_keys=True) + "\n").encode(),
            "swarm001.diff": data["diff"].encode()}


def export(history, run_id, output):
    data = stored(history, run_id)
    root = Path(output).resolve() / run_id
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise ValueError("symlinked evidence directory")
    files = files_for(data)
    manifest = {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}
    files["manifest.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    # Publish manifest last. A partial export never passes verify().
    for name, content in files.items():
        temporary = root / ("." + name + "." + uuid4().hex + ".tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, root / name)
        finally:
            temporary.unlink(missing_ok=True)
    verify(history, run_id, output)
    return root


def verify(history, run_id, output):
    root = Path(output) / run_id
    expected = files_for(stored(history, run_id))
    manifest = json.loads((root / "manifest.json").read_text())
    for name, content in expected.items():
        actual = (root / name).read_bytes()
        if actual != content or manifest.get(name) != hashlib.sha256(content).hexdigest():
            raise ValueError(f"evidence mismatch: {name}")
    return True
