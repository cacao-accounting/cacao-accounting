# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Utilidades para el servicio de importación."""

from datetime import datetime, timedelta
from cacao_accounting.database import database
from cacao_accounting.imports.models import ImportBatch, ImportBatchError


def recover_crashed_batches():
    """Busca lotes que quedaron en estado 'procesando' por mucho tiempo y los marca como fallidos."""
    # Consideramos timeout después de 4 horas
    timeout_limit = datetime.now() - timedelta(hours=4)

    batches = ImportBatch.query.filter(ImportBatch.import_status == 4, ImportBatch.started_at < timeout_limit).all()

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
