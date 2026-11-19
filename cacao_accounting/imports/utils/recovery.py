# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Utilidades para el servicio de importación."""

from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import inspect, select, update
from sqlalchemy.engine import CursorResult

from cacao_accounting.database import database
from cacao_accounting.imports.models import ImportBatch, ImportBatchError


def _import_tables_exist() -> bool:
    """Indica si las tablas requeridas para recuperar importaciones existen."""
    inspector = inspect(database.engine)
    return inspector.has_table(ImportBatch.__tablename__) and inspector.has_table(ImportBatchError.__tablename__)


def _expired_batch_ids(timeout_limit: datetime) -> list[str]:
    """Devuelve los lotes en proceso que excedieron el tiempo límite."""
    return list(
        database.session.execute(
            select(ImportBatch.id).where(
                ImportBatch.import_status == 4,
                (ImportBatch.started_at.is_(None)) | (ImportBatch.started_at < timeout_limit),
            )
        ).scalars()
    )


def _claim_expired_batch(batch_id: str, timeout_limit: datetime) -> bool:
    """Marca el lote como fallido solo si sigue vencido en el momento del claim.

    La actualización condicional evita que dos recuperaciones concurrentes
    procesen el mismo lote y dupliquen el error ``SYSTEM_TIMEOUT`` (#1669).
    """
    claimed = cast(
        CursorResult,
        database.session.execute(
            update(ImportBatch)
            .where(
                ImportBatch.id == batch_id,
                ImportBatch.import_status == 4,
                (ImportBatch.started_at.is_(None)) | (ImportBatch.started_at < timeout_limit),
            )
            .values(import_status=7)
            .execution_options(synchronize_session=False)
        ),
    ).rowcount
    return bool(claimed)


def recover_crashed_batches() -> int:
    """Marca como fallidos los lotes de importación que excedieron el tiempo límite."""
    if not _import_tables_exist():
        return 0

    # Las columnas son DateTime sin zona: el corte debe ser UTC ingenuo.
    timeout_limit = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=4)
    recovered = 0
    for batch_id in _expired_batch_ids(timeout_limit):
        if not _claim_expired_batch(batch_id, timeout_limit):
            continue
        database.session.add(
            ImportBatchError(
                batch_id=batch_id,
                error_type="SYSTEM_TIMEOUT",
                message="El proceso de importación se interrumpió inesperadamente o excedió el tiempo límite (4h).",
            )
        )
        recovered += 1

    if not recovered:
        database.session.rollback()
        return 0
    database.session.commit()
    return recovered
