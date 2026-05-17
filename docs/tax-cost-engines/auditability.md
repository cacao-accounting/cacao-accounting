# Auditability & Snapshots

Every calculation performed by the engines is auditable and reproducible.

## Snapshots

When a document is **Confirmed**, the system saves a JSON Snapshot of the entire calculation context and results.

### Purpose of Snapshots

1. **Historical Reproducibility**: If tax rules change in the future, the document retains its original calculation.
2. **Reversal (Credit Notes)**: When a credit note is issued against a past invoice, the system uses the Snapshot to ensure the reversal amounts match the original ones exactly.
