# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Replace legacy plaintext authentication secrets with keyed digests."""

from __future__ import annotations

import base64
import hashlib
import hmac

import sqlalchemy as sa
from alembic import op
from flask import current_app

revision = "20261113_0002"
down_revision: str | None = "20260809_0001"
branch_labels: str | None = None
depends_on: str | None = None


def _digest(key: bytes, secret_type: str, user_id: str, secret: str, purpose: str = "") -> bytes:
    """Return the same context-bound digest representation as the auth service."""
    payload = "\0".join((secret_type, user_id, purpose, secret)).encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).digest()


def _signing_key() -> bytes:
    """Read the configured application key required to migrate live tokens."""
    key = current_app.secret_key
    if not current_app.config.get("AUTH_TOKEN_KEY_STABLE", False):
        raise RuntimeError("A stable Flask SECRET_KEY is required to migrate authentication secrets")
    if isinstance(key, str):
        key = key.encode("utf-8")
    if not isinstance(key, bytes) or not key:
        raise RuntimeError("A Flask SECRET_KEY is required to migrate authentication secrets")
    return key


def _create_issuance_lock_table() -> None:
    """Create the cross-process serialization table when upgrading an old schema."""
    connection = op.get_bind()
    if sa.inspect(connection).has_table("auth_secret_issuance_lock"):
        return
    op.create_table(
        "auth_secret_issuance_lock",
        sa.Column(
            "user_id",
            sa.String(26),
            sa.ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"),
            primary_key=True,
        ),
    )


def _migrate_otp_codes(connection, key: bytes) -> None:
    """Replace pending and historical six-digit OTP values in place."""
    table = "otp_verification"
    if not sa.inspect(connection).has_table(table):
        return
    otp_table = sa.table(
        table,
        sa.column("id"),
        sa.column("user_id"),
        sa.column("purpose"),
        sa.column("code"),
    )
    rows = connection.execute(sa.select(otp_table)).mappings().all()
    for row in rows:
        code = row["code"]
        if code.startswith("$"):
            continue
        digest = base64.urlsafe_b64encode(_digest(key, "otp", row["user_id"], code, row["purpose"])).decode("ascii")
        connection.execute(sa.update(otp_table).where(otp_table.c.id == row["id"]).values(code=f"${digest[:5]}"))


def _migrate_device_tokens(connection, key: bytes) -> None:
    """Replace recognized-device cookies without revoking their holders."""
    table = "recognized_device"
    if not sa.inspect(connection).has_table(table):
        return
    device_table = sa.table(table, sa.column("id"), sa.column("user_id"), sa.column("token"))
    rows = connection.execute(sa.select(device_table)).mappings().all()
    for row in rows:
        token = row["token"]
        if token.startswith("$"):
            continue
        digest = base64.urlsafe_b64encode(_digest(key, "device", row["user_id"], token)[:27]).decode("ascii")
        value = f"${digest[:35]}"
        connection.execute(sa.update(device_table).where(device_table.c.id == row["id"]).values(token=value))


def _migrate_password_reset_tokens(connection, key: bytes) -> None:
    """Replace bearer reset tokens while preserving unexpired links."""
    table = "password_reset_token"
    if not sa.inspect(connection).has_table(table):
        return
    reset_table = sa.table(table, sa.column("id"), sa.column("token"))
    rows = connection.execute(sa.select(reset_table)).mappings().all()
    for row in rows:
        token = row["token"]
        if token.startswith("$"):
            continue
        value = f"${_digest(key, 'password-reset', '', token).hex()[:63]}"
        connection.execute(sa.update(reset_table).where(reset_table.c.id == row["id"]).values(token=value))


def upgrade() -> None:
    """Convert existing secrets transactionally using the configured key."""
    key = _signing_key()
    connection = op.get_bind()
    _create_issuance_lock_table()
    _migrate_otp_codes(connection, key)
    _migrate_device_tokens(connection, key)
    _migrate_password_reset_tokens(connection, key)


def downgrade() -> None:
    """Refuse downgrade because bearer secrets cannot be recovered from digests."""
    raise RuntimeError("Authentication-secret digests are irreversible; do not downgrade this migration.")
