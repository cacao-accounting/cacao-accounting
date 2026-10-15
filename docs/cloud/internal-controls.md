# Cloud internal-control evidence

Cacao supports customer ICFR controls; it does not certify SOX compliance.

The Cloud application records sensitive configuration changes and financial document
transitions in `audit_trail`, using the same database transaction as the change.

## Audit hash chain

New `audit_trail` rows carry `payload_hash` (SHA-256 of the row's canonical
content) and `prev_hash` (the previous row's `payload_hash`, ordered by the
monotonic ULID id). `cacao_accounting.audit_chain.verify_audit_trail_chain()`
recalculates every hash and validates the links, so editing or removing
historical rows is detected. Rows stored before this feature enablement have
no hash and are excluded from verification. Concurrent PostgreSQL writers may
read the same `prev_hash` before the other transaction commits and produce an
apparent fork; SQLite is unaffected. Database-level immutability (see the
PostgreSQL grants below) remains the primary tamper protection; the hash chain
is the detection layer.

Automated services should wrap work in
`with audit_actor(user_id=None, name="job:exchange-import"):` from
`internal_control_service`. Without an authenticated or explicit actor, automatic
changes are identified as `system`. Never use a shared human account for a job.

The application rejects mutation of audit evidence and posted financial values.
These protections are additional to service authorization; the database runtime
role must also be restricted. SQLite Desktop requires no separate service.

## PostgreSQL deployment

Use separate migration owner and runtime roles. The runtime role must NOT own
tables, inherit the owner role, be superuser, or have schema CREATE privileges.
Run migrations with the owner credential, then execute the following as owner,
replacing `cacao_runtime` with the dedicated runtime role:

```sql
GRANT SELECT, INSERT ON audit_trail, approval_action, audit_log TO cacao_runtime;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_trail, approval_action, audit_log
  FROM cacao_runtime, PUBLIC;
```

Remove equivalent privileges inherited through other role memberships. Grant
normal business table permissions separately. Never grant `ALL ON ALL TABLES`
to the runtime role after this restriction. Test under the runtime credential
that SELECT/INSERT work and UPDATE/DELETE/TRUNCATE fail for each evidence table.
Check `pg_has_role` membership, table ownership, and privilege inheritance during
provisioning; a REVOKE does not override privileges granted through other roles.

The migration account is unavailable to the running application. Keep deployment
credentials separate from `SQLALCHEMY_DATABASE_URI` and restrict database network
access. A PostgreSQL owner or infrastructure administrator can still alter data.
Retained backups or evidence copies outside that administrator's modification
rights and restoration exercises belong to the SaaS operational controls.

## Four-eyes review and administrator authority

When the four-eyes approval flow is enabled, the system enforces an independent
review by a different user whose approval rank is at least as high as the highest
preparer rank. This means a document prepared by an administrator can only be
approved by another active administrator with the same module/company authority;
there is no implicit manager override.

Operational policy: at least two active administrator users should exist for a
company/module before a four-eyes review is enforced. If only one administrator is
available, the review cannot be completed independently and the document should
remain pending or be reassigned for review. Administrators should not be the
default operators for day-to-day posting activity when the four-eyes policy is
active; they should act as reviewers or approvers, while operational posting is
kept in a separate preparer path.

This default is intentionally strict and auditable: `approver.rank >=
max(preparer.rank)` with a different user, instead of a hidden exception such as
`rank == 3` that would weaken segregation of duties.

## Release verification

Cacao creates its schema with `create_all` (`cacaoctl db init`); no incremental
migration is applied. The columns `roles_access.approval_rank` and
`approval_request.policy_snapshot` / `review_payload` are created with the schema.
Databases built with an older schema must be recreated, or the columns added and the
standard module roles classified manually before enabling four eyes. Historical
preparers are not inferred. Classify custom roles explicitly. Existing approval
requests without provenance are historical evidence, not proof of independent review.

Validate on PostgreSQL with actual runtime credentials as well as SQLite tests.
Record version/commit, reviewer, schema result, and runtime privilege checks in
the deployment record. No automated test can establish production role isolation,
backup retention, or the operating effectiveness of a customer's controls.
