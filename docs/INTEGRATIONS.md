# Integration contracts

## Offline proposal adapter

`examples/proposal.json` is the supported handoff contract for another assistant.
The only variable field is the Planner's bounded plan text. The Implementer still
selects a fixed patch identifier, not executable source supplied by the assistant.
The operator reviews the file and passes its SHA-256 with `--approve-proposal`.
The loader hashes and parses the same bytes, validates all five operations and their
arguments, then dispatches through the existing controller. No API credentials,
external model calls, or autonomous patch generation are implemented.

## Read-only MCP

The server is a deliberately small implementation of the pinned
[2025-11-25 lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
and [tools interface](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

Supported: `initialize`, `notifications/initialized`, `ping`, `tools/list`,
`tools/call` with `inspect_run` and exactly one string `run_id` argument.
Unknown methods/tools are rejected; no batch requests, HTTP transport, resources,
sampling, subscriptions, or model-generated actions are supported. An initialized
notification is required before tool use. EOF closes the server. Input is limited
to 16 KiB per line, output evidence to 256 KiB, and a process handles at most 1,000
input frames. Restart the local process after this cap.

Example client configuration (replace paths with absolute paths on your machine):

```json
{
  "mcpServers": {
    "swarmos": {
      "command": "C:/path/to/SwarmOS/.venv/Scripts/python.exe",
      "args": ["-m", "swarmos", "mcp", "--project", "portfolio", "--database", "C:/path/to/SwarmOS/.swarmos/runs.sqlite3"],
      "cwd": "C:/path/to/SwarmOS"
    }
  }
}
```

Client configuration formats differ; this is a template, not a tested integration
with a named desktop client. The verified boundary is a real local subprocess
handshake and tools listing, plus direct handler tests for scoped reads, rejected
writes/arguments, malformed frames and read-only SQLite. Full MCP conformance and
live Claude/ChatGPT/Ollama interoperability remain unverified.
