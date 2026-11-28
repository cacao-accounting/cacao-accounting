# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1313: la revaluación solo se anula por su flujo dedicado.

El listado genérico de comprobantes no debe revertir las líneas de una
corrida dejándola en estado posted; además, los metadatos de anulación de
la corrida deben ser mutables bajo los controles internos de Cloud.
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from cacao_accounting.contabilidad.journal_service import (
    JournalValidationError,
    cancel_submitted_journal,
)
from cacao_accounting.database import (
    ComprobanteContable,
    ExchangeRevaluation,
    User,
    database,
)

FECHA = date(2026, 5, 15)


def _revaluation_journal() -> str:
    """Crea el comprobante de soporte que produce una revaluación."""
    journal = ComprobanteContable(
        entity="cacao",
        date=FECHA,
        status="submitted",
        voucher_type="exchange_revaluation",
        voucher_id="RUN-1313",
        document_no="REV-1313",
    )
    database.session.add(journal)
    database.session.commit()
    return str(journal.id)


def test_anulacion_generica_del_journal_de_revaluacion_se_bloquea(entorno_contable_aislado):
    """La ruta genérica rechaza el comprobante de soporte de la corrida."""
    app = entorno_contable_aislado.app
    with app.app_context():
        journal_id = _revaluation_journal()

        with pytest.raises(JournalValidationError, match="flujo dedicado"):
            cancel_submitted_journal(journal_id, reason="Intento genérico")

        journal = database.session.get(ComprobanteContable, journal_id)
        assert journal is not None
        assert journal.status == "submitted"


def test_metadatos_de_anulacion_son_mutables_en_cloud(entorno_contable_aislado):
    """Los campos de void de ExchangeRevaluation están permitidos por el guard."""
    app = entorno_contable_aislado.app
    with app.app_context():
        run = ExchangeRevaluation(
            company="cacao",
            posting_date=FECHA,
            run_date=FECHA,
            status="posted",
            docstatus=1,
            document_no="RUN-1313",
        )
        database.session.add(run)
        database.session.commit()
        run_id = str(run.id)

        app.config["MODO_ESCRITORIO"] = False
        app.config["INTERNAL_CONTROLS_ENFORCE"] = True
        try:
            run = database.session.get(ExchangeRevaluation, run_id)
            run.status = "voided"
            run.docstatus = 2
            run.voided_at = datetime.now(timezone.utc)
            run.voided_by = str(database.session.execute(select(User.id).filter_by(user="admin")).scalar_one())
            run.void_reason = "Anulación dedicada"
            run.reversal_journal_id = "JOURNAL-REV-1313"
            database.session.commit()
        finally:
            app.config["INTERNAL_CONTROLS_ENFORCE"] = None
            app.config["MODO_ESCRITORIO"] = True

        saved = database.session.get(ExchangeRevaluation, run_id)
        assert saved is not None
        assert saved.status == "voided"
        assert saved.docstatus == 2
        assert saved.reversal_journal_id == "JOURNAL-REV-1313"
