"""Offline agent handoff: validate a proposal and require its exact digest."""
import hashlib
import json
from pathlib import Path
from .controller import Operation, Role, demo_operations


def load_proposal(path, approval):
    raw = Path(path).read_bytes()
    if len(raw) > 16384:
        raise ValueError('proposal exceeds 16 KiB')
    digest = hashlib.sha256(raw).hexdigest()
    if approval != digest:
        raise ValueError(f'proposal approval required: --approve-proposal {digest}')
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != {'operations'} or not isinstance(data['operations'], list) or len(data['operations']) != 5:
        raise ValueError('proposal must contain exactly five operations')
    operations = []
    for proposed, expected in zip(data['operations'], demo_operations()):
        if not isinstance(proposed, dict) or set(proposed) != {'role', 'tool', 'arguments'}:
            raise ValueError('unexpected proposal fields')
        if proposed['role'] != expected.role.value or proposed['tool'] != expected.tool:
            raise ValueError('proposal changes the required role/tool order')
        args = proposed['arguments']
        if expected.tool == 'propose_plan':
            if not isinstance(args, dict) or set(args) != {'plan'} or not isinstance(args['plan'], str) or not 1 <= len(args['plan'].strip()) <= 2000:
                raise ValueError('plan must be bounded text')
        elif args != dict(expected.arguments):
            raise ValueError('proposal exceeds authorized operation scope')
        operations.append(Operation(Role(proposed['role']), proposed['tool'], args))
    return tuple(operations), digest
