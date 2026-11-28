# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1671: la recuperación compara el inicio con un corte en UTC, no local."""

from __future__ import annotations

from datetime import UTC, datetime

from cacao_accounting.database import Currency, Entity, database
from cacao_accounting.imports.models import ImportBatch
from cacao_accounting.imports.utils import recovery


class RelojConDesfase(datetime):
    """Reloj donde la hora local (UTC-6) y la UTC difieren en seis horas."""

    @classmethod
    def now(cls, tz=None):
        """Devuelve un instante fijo en UTC o el mismo instante en hora local."""
        if tz is None:
            return cls(2026, 11, 1, 15, 0)
        return cls(2026, 11, 1, 21, 0, tzinfo=UTC)


def _lote(company: str, started_at: datetime) -> ImportBatch:
    """Crea un lote en proceso con la marca de inicio indicada."""
    lote = ImportBatch(
        company_id=company,
        record_type="journal_entry",
        source_format="csv",
        source_filename="lote.csv",
        import_status=4,
        started_at=started_at,
    )
    database.session.add(lote)
    database.session.flush()
    return lote


def test_recupera_lote_vencido_aunque_la_hora_local_este_atrasada(app, monkeypatch):
    """Son las 21:00 UTC (15:00 local): un lote de 16:00 UTC ya excedió 4 horas."""
    with app.app_context():
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.add(
            Entity(
                code="alpha-nio",
                name="Alfa NIO",
                company_name="Alfa NIO",
                tax_id="TAX-NIO-1671",
                currency="NIO",
                enabled=True,
            )
        )
        database.session.flush()
        vencido = _lote("alpha-nio", datetime(2026, 11, 1, 16, 0))
        activo = _lote("alpha-nio", datetime(2026, 11, 1, 19, 0))
        database.session.commit()
        vencido_id = vencido.id
        activo_id = activo.id

    monkeypatch.setattr(recovery, "datetime", RelojConDesfase)

    with app.app_context():
        recuperados = recovery.recover_crashed_batches()

        assert recuperados == 1
        assert database.session.get(ImportBatch, vencido_id).import_status == 7
        assert database.session.get(ImportBatch, activo_id).import_status == 4
