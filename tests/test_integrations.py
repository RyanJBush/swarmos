import hashlib
import io
import json
from dataclasses import asdict
import subprocess
import sys
import pytest
from swarmos.controller import demo_operations
from swarmos.proposals import load_proposal
from swarmos.run_history import RunHistory
from swarmos.evidence import payload
from swarmos.controller import BoundedController
from swarmos.mcp_server import Server, serve


def test_proposal_digest_and_scope(tmp_path):
    path = tmp_path / 'proposal.json'
    data = {'operations': [asdict(o) for o in demo_operations()]}
    path.write_text(json.dumps(data))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='approval required'):
        load_proposal(path, None)
    assert len(load_proposal(path, digest)[0]) == 5
    data['operations'][2]['arguments']['files'] = ['../secret']
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='scope'):
        load_proposal(path, hashlib.sha256(path.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match='approval required'):
        load_proposal(path, digest)


def seed(db):
    with RunHistory(db) as h:
        run = h.start()
        result = BoundedController().run([])
        data = payload(run, result)
        data['project'] = 'one'
        h.finish(run, result, data)
        return run.id


def request(method, params=None):
    return {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}


def initialize(server):
    assert 'result' in server.handle(request('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '1'}}))
    server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})


def test_mcp_lifecycle_scope_and_read_only(tmp_path):
    db = tmp_path / 'db'
    run_id = seed(db)
    before = db.read_bytes()
    server = Server(db, 'one')
    try:
        assert 'error' in server.handle(request('tools/list'))
        initialize(server)
        assert [t['name'] for t in server.handle(request('tools/list'))['result']['tools']] == ['inspect_run']
        assert not server.handle(request('tools/call', {'name': 'inspect_run', 'arguments': {'run_id': run_id}}))['result']['isError']
        assert 'error' in server.handle(request('tools/call', {'name': 'apply_patch'}))
        assert 'error' in server.handle(request('tools/call', {'name': 'inspect_run', 'arguments': {'run_id': run_id, 'project': 'other'}}))
        with pytest.raises(Exception):
            server.connection.execute('DELETE FROM swarmos_runs')
    finally:
        server.close()
    other = Server(db, 'two')
    try:
        initialize(other)
        assert other.handle(request('tools/call', {'name': 'inspect_run', 'arguments': {'run_id': run_id}}))['result']['isError']
    finally:
        other.close()
    assert db.read_bytes() == before


def test_stdio_real_subprocess_and_malformed_frames(tmp_path):
    db = tmp_path / 'db'
    seed(db)
    init = request('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'test'}})
    lines = [init, {'jsonrpc': '2.0', 'method': 'notifications/initialized'}, request('tools/list')]
    process = subprocess.run([sys.executable, '-m', 'swarmos', 'mcp', '--database', str(db), '--project', 'one'],
        input='\n'.join(json.dumps(x) for x in lines)+'\n', text=True, capture_output=True, timeout=10)
    assert process.returncode == 0, process.stderr
    responses = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(responses) == 2 and responses[1]['result']['tools'][0]['name'] == 'inspect_run'
    sink = io.StringIO()
    serve(db, 'one', io.StringIO('invalid\n[]\n'), sink)
    assert [json.loads(line)['error']['code'] for line in sink.getvalue().splitlines()] == [-32700, -32600]
    sink = io.StringIO()
    serve(db, 'one', io.StringIO('x'*17000+'\n'), sink)
    assert not sink.getvalue()
