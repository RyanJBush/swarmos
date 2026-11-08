"""Minimal read-only MCP stdio server, pinned to protocol 2025-11-25.

No execution tools, network listener, sampling, or external server installation.
"""
import json
from pathlib import Path
import sqlite3
import sys

TOOL = {'name': 'inspect_run', 'description': 'Read a persisted SwarmOS run in the configured project.',
        'inputSchema': {'type': 'object', 'properties': {'run_id': {'type': 'string', 'maxLength': 36}},
                        'required': ['run_id'], 'additionalProperties': False},
        'annotations': {'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False}}


class Server:
    def __init__(self, database, project):
        self.connection = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)
        self.project = project
        self.initialized = False
        self.ready = False

    def close(self):
        self.connection.close()

    def handle(self, request):
        if not isinstance(request, dict) or request.get('jsonrpc') != '2.0' or not isinstance(request.get('method'), str):
            return {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'Invalid request'}}
        identity = request.get('id')
        method = request['method']
        if 'id' not in request:
            if method == 'notifications/initialized' and self.initialized:
                self.ready = True
            return None
        response = {'jsonrpc': '2.0', 'id': identity}
        params = request.get('params', {})
        try:
            if not isinstance(params, dict):
                raise ValueError('params must be an object')
            if method == 'initialize':
                if self.initialized:
                    raise ValueError('already initialized')
                if not isinstance(params.get('protocolVersion'), str) or not isinstance(params.get('capabilities'), dict) or not isinstance(params.get('clientInfo'), dict):
                    raise ValueError('missing initialization fields')
                self.initialized = True
                result = {'protocolVersion': '2025-11-25', 'capabilities': {'tools': {}},
                          'serverInfo': {'name': 'swarmos-readonly', 'version': '0.2.0'}}
            elif method == 'ping':
                result = {}
            elif not self.ready:
                raise ValueError('initialize and send notifications/initialized first')
            elif method == 'tools/list':
                result = {'tools': [TOOL]}
            elif method == 'tools/call':
                args = params.get('arguments', {})
                if params.get('name') != 'inspect_run':
                    raise ValueError('tool not allowed')
                if not isinstance(args, dict) or set(args) != {'run_id'} or not isinstance(args['run_id'], str) or len(args['run_id']) != 36:
                    raise ValueError('invalid run_id')
                row = self.connection.execute("SELECT payload FROM swarmos_events WHERE run_id=? AND kind='evidence'", (args['run_id'],)).fetchone()
                if row is None or json.loads(row[0]).get('project') != self.project:
                    result = {'content': [{'type': 'text', 'text': 'Run unavailable in configured project.'}], 'isError': True}
                elif len(row[0].encode()) > 262144:
                    result = {'content': [{'type': 'text', 'text': 'Run exceeds response size limit.'}], 'isError': True}
                else:
                    result = {'content': [{'type': 'text', 'text': row[0]}], 'isError': False}
            else:
                return {**response, 'error': {'code': -32601, 'message': 'Method not found'}}
            return {**response, 'result': result}
        except (ValueError, TypeError):
            return {**response, 'error': {'code': -32602, 'message': 'Invalid parameters or lifecycle state'}}
        except sqlite3.Error:
            return {**response, 'error': {'code': -32603, 'message': 'Database unavailable'}}


def serve(database, project, source=None, sink=None):
    source, sink = source or sys.stdin, sink or sys.stdout
    server = Server(database, project)
    try:
        for _ in range(1000):
            line = source.readline(16385)
            if not line:
                break
            if len(line) > 16384:
                break  # Oversized frame closes the process; never execute fragments.
            try:
                response = server.handle(json.loads(line))
            except ValueError:
                response = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Parse error'}}
            if response is not None:
                sink.write(json.dumps(response) + '\n')
                sink.flush()
    finally:
        server.close()
