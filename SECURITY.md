# Security boundaries

SwarmOS enforces application policy, **not an OS sandbox**. Run it as an ordinary
user on trusted local code, using only disposable repositories it creates.

| Boundary | Enforcement | Remaining limitation |
|---|---|---|
| Roles/tools | Static role allowlists and exact successful sequence | Python process owner can modify policy |
| Writes | Fixed `src/labels.py` patch in an owned fixture; path/symlink checks | No isolation from privileged local races or hostile filesystem changes |
| Review | Trusted test path/hash, fixed pytest invocation, 30-second subprocess timeout | Test process inherits the host environment; no network/resource sandbox |
| Proposal | 16 KiB cap, exact operation schema, SHA-256 approval | Approval requires a human to review the bytes |
| Memory | Project/task key; reviewed source run; bounded advisory fact | Project labels are scoping, not authenticated multi-tenant authorization |
| MCP | Read-only SQLite, one tool, project filter, bounded frames/responses | Local users with database access can read or alter data outside this interface |
| Evidence | Transactional authoritative payload; hash/byte verification of exports | Hashes are not signatures; database tampering is outside the trust model |
| Timeline | Escaped text; offline HTML without scripts or remote resources | Generated views may be edited by the file owner |

No credential is required. Do not put credentials, personal repositories, secrets,
or production data into fixture paths, proposals, or error messages. Git and pytest
execute on the host and inherit environment/configuration; pytest plugins and Git
configuration are trusted dependencies. Do not expose this process as a public service.

Generated artifacts, SQLite journals, environments and common credential patterns
are ignored. A filename/pattern scan cannot prove that no secret exists. Review the
full staged diff before any first push. CI uses read-only repository permissions.
Remote publication and visibility changes require owner approval.
