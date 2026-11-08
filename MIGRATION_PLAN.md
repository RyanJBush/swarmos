# SwarmOS SQLite to Azure SQL Migration Plan

## Readiness

**Status: blocked for execution.** This is an application replatform from SQLite to
Azure SQL Database, not a SQL Server backup, BACPAC, or log-replay migration. The
recommended target is Azure SQL Database General Purpose:

- Serverless General Purpose for development or intermittent workloads.
- Provisioned General Purpose for production, after workload measurements.

The current assessment found a SQLite 3.50.4 application with five domain tables,
one migration-history table, one migration-lock table, no production data file, no
HTTP endpoint, no Azure SQL driver, and no workload telemetry. The repository test
baseline is currently `3 passed`.

## Scope and Target

The source schema is defined in `swarmos/persistence.py`:

| Source table                | Azure SQL target                | Required conversion                                                                                                |
| --------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `swarmos_workflows`         | `[swarmos].[workflows]`         | UUID text to `uniqueidentifier`; text fields to explicit `nvarchar` sizes; timestamp to `datetime2(7)`             |
| `swarmos_agents`            | `[swarmos].[agents]`            | UUID and timestamp conversion; preserve unique name                                                                |
| `swarmos_runs`              | `[swarmos].[runs]`              | UUID conversion; `status` check constraint; workflow foreign key                                                   |
| `swarmos_tasks`             | `[swarmos].[tasks]`             | UUID conversion; integer position; run and agent foreign keys; cascade delete; `(run_id, position)` uniqueness     |
| `swarmos_events`            | `[swarmos].[events]`            | UUID conversion; explicit event sequence; payload mapped to `nvarchar(max)` or native `json` after contract review |
| `swarmos_schema_migrations` | `[swarmos].[schema_migrations]` | Replace SQLite metadata with Azure SQL migration metadata                                                          |
| `swarmos_migration_lock`    | `[swarmos].[migration_lock]`    | Replace with an Azure SQL application-lock strategy                                                                |

The Azure SQL database must contain a real `[swarmos]` schema. The current
`swarmos_` prefix is a SQLite namespace workaround and should not be carried as
the long-term Azure SQL naming convention.

## Blockers Before Build

These are go/no-go items, not optional cleanup:

1. **Source data is missing.** Locate the real SQLite file, record its size,
   table row counts, maximum text lengths, foreign-key violations, duplicate
   candidates, and a checksum/export manifest.
2. **Target identity is missing.** Choose the Azure subscription, region,
   database name, networking mode, authentication model, backup retention, and
   recovery objectives. Do not put credentials in the repository.
3. **Workload evidence is missing.** Capture request volume, concurrent writers,
   read/write mix, latency percentiles, database file growth, and peak lock or
   checkpoint behavior. Do not finalize a production SKU from the empty schema.
4. **Application surface is incomplete.** Implement or identify the real HTTP
   endpoints and the caller contract before cutover testing.
5. **Driver and deployment path are missing.** Select the Python Azure SQL driver,
   define environment-based configuration, and test TLS/authentication from the
   intended runtime.

## Migration Approach

Use a **custom offline logical export/import with a short maintenance window**.
This is the appropriate first approach because the source is SQLite, the assessed
dataset is empty, and SQLite has no supported Azure SQL log-replay or BACPAC path.

Do not use:

- SQL Server backup/restore or BACPAC tooling against the SQLite file.
- Azure SQL Managed Instance, Hyperscale, or a SQL VM without new evidence that
  requires their capabilities.
- Dual-write during cutover. It creates reconciliation and split-brain risk.

## Ordered Execution Plan

### 0. Go/no-go discovery

**Owner:** application owner and DBA

- Identify the source SQLite file and freeze its location.
- Record the source schema, row counts, file size, indexes, constraints, and
  representative data statistics.
- Capture application and workload metrics for a representative period.
- Confirm target region, data residency, RPO, RTO, downtime window, and rollback
  authority.

**Checkpoint:** proceed only when the source file, data inventory, workload
baseline, target region, and downtime window are recorded. Otherwise remain
`blocked`.

### 1. Provision an isolated Azure SQL staging database

**Owner:** platform/DBA

- Create a staging Azure SQL Database in the selected region.
- Use a private endpoint or approved firewall path, TLS, and Microsoft Entra
  authentication where available.
- Create the `[swarmos]` schema and least-privilege application principal.
- Configure backup retention and diagnostic settings.
- Record the database compatibility level and service tier.

**Checkpoint:** the application runtime can connect to staging, can run a simple
`SELECT 1`, and cannot access an unrelated database or schema.

### 2. Build the target schema and migration runner

**Owner:** application and DBA

- Replace SQLite DDL with Azure SQL DDL under `[swarmos]`.
- Replace `sqlite_master`, `PRAGMA`, `BEGIN IMMEDIATE`, and SQLite-specific
  statement splitting.
- Store migration versions and checksums in `[swarmos].[schema_migrations]`.
- Serialize migration execution with `sp_getapplock` or an equivalent database
  lock, and commit each migration atomically.
- Make the migration runner fail on checksum drift, missing required objects,
  unsupported SQL, or a partially applied migration.
- Add an explicit monotonically increasing `event_sequence` to `events`; do not
  port the current `ORDER BY rowid` behavior.
- Add an index for event reads, for example `(run_id, event_sequence)`.

**Checkpoint:** a clean staging database can migrate from empty to current in a
single run; a second run is a no-op; an injected failure leaves no migration
history row or partial target schema; and every repository query succeeds against
Azure SQL.

### 3. Implement and test the Azure SQL data-access adapter

**Owner:** application team

- Replace direct `sqlite3` connections with the selected Azure SQL driver.
- Keep parameters bound; do not concatenate IDs or status values into SQL.
- Preserve foreign keys, status checks, unique names, task ordering, and cascade
  behavior.
- Map UUIDs, timestamps, text lengths, and JSON/payload data explicitly.
- Add connection retry only at the connection/transient-failure boundary; do not
  retry non-idempotent writes without an idempotency key.
- Add query timing and request correlation IDs before load testing.

**Checkpoint:** repository contract tests pass against staging, including invalid
foreign keys, duplicate names, duplicate task positions, event ordering, and
rollback of failed writes.

### 4. Rehearse the data transfer

**Owner:** DBA and application team

- Put the application into a write-quiesced state or use a maintenance build.
- Export SQLite rows in foreign-key order: workflows and agents, then runs, then
  tasks and events.
- Transform IDs, timestamps, payloads, and event sequence values.
- Load the staging database using parameterized bulk inserts or batched inserts.
- Preserve the source-to-target ID map if any values require transformation.
- Validate row counts, null counts, uniqueness, foreign keys, status domains,
  timestamp ranges, payload validity, and aggregate checksums.

**Checkpoint:** two independent validation runs agree, and the application smoke
test reads the same logical records from staging as from a frozen SQLite copy.

### 5. Performance and failure rehearsal

**Owner:** application team and DBA

- Replay representative reads and writes at measured concurrency.
- Capture latency percentiles, CPU, data/log I/O, waits, connection pool behavior,
  and transaction failures.
- Confirm the event query uses the new `(run_id, event_sequence)` index.
- Test transient disconnects, deadlocks/timeouts, duplicate writes, and migration
  retries.
- Resize the General Purpose tier only after observing this workload.

**Checkpoint:** measured latency and error rates meet the agreed SLO, the target
remains within RPO/RTO, and no required query relies on SQLite-only behavior.

### 6. Production cutover

**Owner:** release manager, DBA, and application owner

- Announce the maintenance window and stop new writes to SQLite.
- Drain in-flight requests and take a final immutable SQLite copy.
- Run the final export/import and validation checks.
- Record source row counts and checksums before switching traffic.
- Apply any pending Azure SQL migrations.
- Change the application configuration to the Azure SQL connection setting.
- Start the application against Azure SQL and run smoke tests for create, read,
  update, task ordering, event creation, and invalid foreign-key behavior.
- Re-enable traffic only after smoke tests and target health checks pass.

**Checkpoint:** the application is serving from Azure SQL, the final validation
manifest matches, and the old SQLite copy is retained read-only for rollback.

### 7. Stabilization and completion

**Owner:** operations

- Monitor application latency, errors, connection failures, locks, CPU, I/O, and
  storage growth for the agreed observation window.
- Compare the post-cutover workload with the rehearsal baseline.
- Keep the SQLite source snapshot until the rollback retention period expires.
- Document the Azure SQL backup, restore, alerting, migration, and ownership model.

**Exit checkpoint:** no unresolved severity-one or severity-two defects, validation
evidence is archived, and the rollback window has formally closed.

## Validation Manifest

Archive these artifacts for each rehearsal and production cutover:

- Source SQLite file hash and immutable-copy location.
- Source and target schema snapshots.
- Per-table row counts and null counts.
- Primary/unique key checks and foreign-key validation results.
- Aggregate checksums for stable business columns.
- Migration version and checksum records.
- Query plan evidence for the critical repository reads.
- Application smoke-test results and request correlation IDs.
- Performance comparison: p50, p95, p99, throughput, errors, CPU, I/O, and waits.

A cutover is not successful if the migration command exits zero but any validation
artifact is missing or inconsistent.

## Rollback

Rollback is a connection switch, not a reverse migration:

1. Keep the final SQLite snapshot untouched and retain the prior application build.
2. If Azure SQL fails before new writes are accepted, stop the new build and point
   the application back to the frozen SQLite copy.
3. If Azure SQL accepted writes, do not immediately point back to SQLite. First
   stop traffic, export the accepted target changes, reconcile them against the
   source snapshot, and obtain an explicit recovery decision.
4. Restore the previous application configuration only after the data owner
   confirms the rollback dataset is complete.
5. Record the failed cutover, target diagnostics, and reconciliation outcome before
   attempting another migration.

The rollback plan is invalid if both databases remain writable or if the only
SQLite copy is modified after the final export.

## Immediate Actions

1. Locate and checksum the real SQLite database.
2. Provide source row counts, file size, growth, request volume, latency, and
   concurrency measurements.
3. Choose the Azure region, authentication model, networking model, RPO/RTO, and
   downtime window.
4. Confirm whether payloads are plain text or JSON and define maximum lengths.
5. Implement the actual application endpoint and Azure SQL adapter.
6. Create a staging Azure SQL Database and run the first schema conversion.
7. Rehearse export, import, validation, and rollback before scheduling production
   cutover.
