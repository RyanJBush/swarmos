# Client verification — November 7, 2026

Client: **Claude Code 2.1.319**, installed Windows executable.
Server: SwarmOS read-only stdio MCP server, configured with the `recruiter-demo`
project and a locally generated run database.

The test used a separate `CLAUDE_CONFIG_DIR` inside `.swarmos/claude-check`, leaving
the user's normal Claude configuration unchanged. A server configuration was added
with `claude mcp add-json --scope user swarmos ...` inside that isolated directory.
`claude mcp get swarmos` returned exit code 0 and **Status: Connected**.
No model prompt, API call, or paid inference was requested.

This verifies real Claude Code connection/initialization, not model-driven tool
selection or an end-to-end Claude conversation. The existing subprocess and handler
tests verify tools listing, scoped run retrieval, rejection behavior, and read-only
SQLite. Claude Desktop was not configured or tested.

A separate Python MCP SDK 1.30.0 attempt stalled in this Windows environment and
was stopped. It is not counted as a successful integration check; no unverified
SDK helper is shipped. The initial attempt to pass session-only MCP flags to a
Claude mcp subcommand was rejected; isolated user-scope configuration was the
successful method.

## Reproduce with an isolated Claude configuration

From the repository root after generating a demo for `recruiter-demo`, set
`CLAUDE_CONFIG_DIR` to a disposable project-local directory and use the JSON
configuration format in INTEGRATIONS.md. Run `claude mcp add-json --scope user
swarmos <JSON>` and `claude mcp get swarmos`. Use absolute Python/database paths
and set `PYTHONPATH` to this checkout in the server environment.
The scope is only isolated while that environment variable is set. Do not paste
machine-specific paths into a shared configuration.
