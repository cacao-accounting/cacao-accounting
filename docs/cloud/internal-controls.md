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

Since Cacao 20261015 the hash (chain version 2) includes the row's own ULID in
the canonical payload, so duplicating a row's payload at another position is
detected. Rows stamped before the feature carry `hash_version NULL` and are
verified with the legacy format; no historical data is rewritten.

Concurrent PostgreSQL writer forks are not yet serialized; see issue #926 for
the hardening roadmap.

### Operational verification

`cacaoctl audit-verify` runs `verify_audit_trail_chain()` against the active
database and reports findings (`payload_tampered`, `chain_break`) with the row
id and exits 1 when findings exist. It is intended to be wired as a periodic
job (cron/systemd timer/scheduler) plus monitoring, so missing execution is
alerted as well:

```cron
# every 30 minutes; the command exits 1 when findings exist.
*/30 * * * * cacaoctl audit-verify || alert-audit-chain
```

Response playbook when the command reports findings:

1. Freeze access that could rewrite `audit_trail` (restrict the runtime role,
   block application instances against the database).
2. Take a full backup before any repair attempt; never edit rows in place.
3. Verify whether `document_type`/`document_id` referenced rows are missing
   (`chain_break` usually means a row was deleted in the middle of the chain).
4. Compare `before_json`/`after_json` of the surrounding rows to establish the
   real sequence; use the healthy tail (rows with `payload_hash NULL`) as
   anchor.
5. Escalate to an incident review per the data-integrity policy. Detection is
   the contract of the command; the application never rehashes historical
   rows.

Automated services should wrap work in
`with audit_actor(user_id=None, name="job:exchange-import"):` from
`internal_control_service`. Without an authenticated or explicit actor, automatic
changes are identified as `system`. Never use a shared human account for a job.

The application rejects mutation of audit evidence and posted financial values.
These protections are additional to service authorization; the database runtime
role must also be restricted. SQLite Desktop requires no separate service.

## Approval and configuration evidence

`cacao_accounting.internal_control_service` installs the shared guards. Every
change to a sensitive model (users, roles, company access, entities, exchange
rates, accounting periods and fiscal years, taxes and tax rules, accounting
mapping rules and default accounts, books and accounts, and purchase/sales
matching configuration) is written to `audit_trail` in the same transaction as
the change, with before/after values and the resolved actor.

Sensitive `cacao_config` keys are recognized by prefix (`approval_`,
`four_eyes_`, `fiscal_`, `accounting_`). The row identity is the key, so the
guard resolves the persisted key before a rename: renaming a sensitive key still
produces the audit event and keeps the company scope of the previous key.
Direct Core `UPDATE`/`DELETE` on `cacao_config` is rejected because the sensitive
identity lives in the `WHERE` clause, not in the mutated columns; only the
audited ORM path may edit it.

Approval requests carry provenance that is immutable: `policy_snapshot`,
`review_payload`, `requested_by`, `company_id`, `required_level`, the document
identity and the creation/cancellation stamps cannot be changed or deleted
through the ORM or Core. Only lifecycle moves (`status`, `current_level`) are
allowed, and only for the specific rows handed to
`approval_request_transition(...)`. Bulk ORM updates (`do_orm_execute`) are
rejected as well, so a configuration or approval snapshot cannot be skipped.

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

The same restriction applies to the inter-voucher flow evidence tables
(`document_relation`, `purchase_reconciliation`, `purchase_reconciliation_item`,
`purchase_invoice_receipt_allocation`, `purchase_receipt_return_allocation`,
`purchase_credit_note_allocation`). The application may append new relations and
write the audited workflow transitions (`status` and the reversal/cancellation
stamps) through its authorized services, but no direct rewrites of link,
quantity or matching-calculus fields are acceptable under any circumstance:

```sql
GRANT SELECT, INSERT ON document_relation, purchase_reconciliation,
  purchase_reconciliation_item, purchase_invoice_receipt_allocation,
  purchase_receipt_return_allocation, purchase_credit_note_allocation
  TO cacao_runtime;
GRANT SELECT, UPDATE ON document_relation, purchase_reconciliation,
  purchase_reconciliation_item, purchase_invoice_receipt_allocation,
  purchase_receipt_return_allocation, purchase_credit_note_allocation
  TO cacao_runtime;
REVOKE DELETE, TRUNCATE ON document_relation, purchase_reconciliation,
  purchase_reconciliation_item, purchase_invoice_receipt_allocation,
  purchase_receipt_return_allocation, purchase_credit_note_allocation
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
## Matching configuration approvals

The policy approved in issue #924 is simple: every effective change to
purchase or sales matching configuration requires independent approval
when the Cloud approval engine and independent review are enabled. This
includes increases, reductions, changes of tolerance type and changes that
strengthen controls. There is no weakening/strengthening classification.

Saving identical values does not create a proposal; numerically equal
decimals (for example, `5` and `5.0000`) are identical values. Pending
changes do not alter the active configuration. Another authorized reviewer
must approve them, and a changed baseline prevents applying a stale
proposal. Audit evidence retains the before/after values, actor and company.

Desktop retains its single-user operation. Cloud authorization remains
mandatory even if the approval engine is disabled. Historical matching
snapshots remain unchanged when the active configuration changes.
