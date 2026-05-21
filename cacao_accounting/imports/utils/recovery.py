# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Utilidades para el servicio de importación."""

from datetime import datetime, timedelta

from sqlalchemy import inspect

from cacao_accounting.database import database
from cacao_accounting.imports.models import ImportBatch, ImportBatchError


def _import_tables_exist() -> bool:
    """Indica si las tablas requeridas para recuperar importaciones existen."""
    inspector = inspect(database.engine)
    return inspector.has_table(ImportBatch.__tablename__) and inspector.has_table(ImportBatchError.__tablename__)


def recover_crashed_batches() -> int:
    """Marca como fallidos los lotes de importación que excedieron el tiempo límite."""
    if not _import_tables_exist():
        return 0

    timeout_limit = datetime.now() - timedelta(hours=4)

    batches = ImportBatch.query.filter(ImportBatch.import_status == 4, ImportBatch.started_at < timeout_limit).all()
    if not batches:
        return 0

    for batch in batches:
        batch.import_status = 7  # Fallido
        error = ImportBatchError(
            batch_id=batch.id,
            error_type="SYSTEM_TIMEOUT",
            message="El proceso de importación se interrumpió inesperadamente o excedió el tiempo límite (4h).",
        )
        database.session.add(error)
        database.session.add(batch)

    database.session.commit()
    return len(batches)
