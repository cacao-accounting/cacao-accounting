# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Agrega ``user.api_credential_hash`` para credenciales de integración.

La credencial de integración comparte la validación JWT con el navegador,
pero necesita una huella propia: el login reemplaza ``api_token_hash`` en
cada acceso y no debe invalidar la integración (#2285). Las filas heredadas
quedan con ``NULL`` y simplemente no tienen credencial de integración.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20261128_0001"
down_revision: str | None = "20261127_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Agrega ``user.api_credential_hash`` si la tabla existe y falta la columna."""
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("user"):
        return
    columns = {column["name"] for column in inspector.get_columns("user")}
    if "api_credential_hash" not in columns:
        op.add_column("user", sa.Column("api_credential_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    """Retira ``user.api_credential_hash`` si existe."""
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("user"):
        return
    columns = {column["name"] for column in inspector.get_columns("user")}
    if "api_credential_hash" in columns:
        op.drop_column("user", "api_credential_hash")
