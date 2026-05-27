# Document Validation via QR

The QR validation functionality allows a third party to confirm that a document was emitted by Cacao Accounting and that its main data has not been altered.

## How it works

1. When an official document is posted, Cacao generates or reuses a secure public token and stores a deterministic SHA256 hash of the allowed validation payload.
2. The print backend injects `validation.enabled`, `validation.public_url`, `validation.token` and `validation.qr_data_uri` into the Jinja context. Templates must never build validation URLs by themselves.
3. Scanning the QR opens `/public/validate_doc/<token>`, which recalculates the hash from the current database state and renders a public-safe view model.

Draft documents never create or update public validation records. Cancelled and reverted documents keep their token, but the public status changes.

## Configuration

External document validation is managed from **Administration -> Configuration -> External Document Validation**.

The settings are persisted in `CacaoConfig`:

- `external_document_validation_enabled`: enables public validation endpoint, URL injection and QR rendering.
- `external_document_validation_base_url`: base URL used to build public validation links.

If `external_document_validation_base_url` is missing or empty, Cacao uses `https://cacaocontent.com`. Environment values such as `EXTERNAL_DOCUMENT_VALIDATION_ENABLED` and `EXTERNAL_DOCUMENT_VALIDATION_BASE_URL` are only bootstrap fallbacks when no persisted setting exists.

## QR dependency

QR generation uses `segno==1.6.6`, declared in `requirements.txt`. Missing QR support is a deployment error: the backend raises a clear runtime error instead of silently hiding the QR feature.

Template publication validates QR rendering when the body references `validation.qr_data_uri`, so a broken QR dependency is detected before the format is published.

## Technical statuses

The validation backend returns technical statuses:

- `valid`: the current document hash matches the stored validation hash.
- `invalid`: the document exists, but the current hash differs.
- `unavailable`: the token does not exist, is disabled or the source document is unavailable.
- `cancelled`: the source document was cancelled.
- `reverted`: the source document was reverted.

The public template translates these statuses into human-readable labels.

## Public data contract

The public page may show only this view model:

- company name
- company tax id
- document type
- document number
- document date
- currency
- total
- document status
- validation time

It must not expose GL accounts, internal notes, line-level detail, user IDs, private relations or raw SQLAlchemy objects.

## Security

- Tokens are non-predictable.
- The canonical hash includes only an allowlist of validation-safe fields.
- The system does not store snapshots of the PDF or HTML; it validates against the current database state.
- When global validation is disabled, Cacao does not build `public_url`, contextual token or renderable QR data.
