# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1203: la recuperación incluye lotes en proceso sin `started_at`."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.database import Currency, Entity, database
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services.import_service import ImportService
from cacao_accounting.imports.utils.recovery import recover_crashed_batches


def test_lote_en_proceso_sin_marca_se_recupera(app):
    """Un lote en estado 4 sin `started_at` no queda zombi."""
    sufijo = uuid4().hex[:6]
    with app.app_context():
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        if database.session.execute(database.select(Entity).filter_by(code="alpha")).scalar_one_or_none() is None:
            database.session.add(
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Alfa {sufijo}",
                    tax_id=f"TAX-{sufijo}",
                    currency="NIO",
                    enabled=True,
                )
            )
        database.session.flush()
        lote = ImportBatch(
            company_id="alpha",
            record_type="journal_entry",
            source_format="csv",
            source_filename="lote.csv",
            import_status=4,
            started_at=None,
        )
        database.session.add(lote)
        database.session.commit()
        lote_id = lote.id

    with app.app_context():
        recuperados = recover_crashed_batches()

        assert recuperados >= 1
        persistido = database.session.get(ImportBatch, lote_id)
        assert persistido.import_status == 7
        errores = database.session.execute(database.select(ImportBatchError).filter_by(batch_id=lote_id)).scalars().all()
        assert len(errores) == 1
        assert errores[0].error_type == "SYSTEM_TIMEOUT"


def test_worker_no_persiste_documento_si_recovery_ya_gano(app, entorno_contable):
    """Un lote recuperado no puede crear documentos financieros tardíos."""
    with app.app_context():
        lote = ImportBatch(
            company_id="cacao",
            record_type="journal_entry",
            source_format="csv",
            source_filename="lote.csv",
            import_status=7,
            started_at=None,
        )
        database.session.add(lote)
        database.session.commit()
        lote_id = lote.id
        persistencias = []

        class Adapter:
            """Registra si el worker intentó persistir después de perder el lote."""

            @staticmethod
            def build_document(rows, context):
                return {}

            @staticmethod
            def persist_document(document):
                persistencias.append(document)

        resultado = ImportService()._process_document(Adapter(), "doc-1", [{}], {}, lote, lote_id)

        assert resultado is None
        assert persistencias == []
        assert lote.import_status == 7
        errores = database.session.execute(database.select(ImportBatchError).filter_by(batch_id=lote_id)).scalars().all()
        assert errores == []
