# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1734: cambiar la serie de un contador actualiza todos sus mapeos N:M."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.contabilidad.services import _sync_counter_naming_series_map
from cacao_accounting.database import (
    ExternalCounter,
    NamingSeries,
    SeriesExternalCounterMap,
    database,
)


def test_cambiar_serie_actualiza_todos_los_mapeos_del_contador(app):
    """Dos condiciones distintas no producen MultipleResultsFound y se renombran."""
    sufijo = uuid4().hex[:6]
    with app.app_context():
        actual = NamingSeries(
            name=f"Serie actual {sufijo}",
            entity_type="bank_payment",
            company="cacao",
            prefix_template="PAG-*YYYY*-",
        )
        nueva = NamingSeries(
            name=f"Serie nueva {sufijo}",
            entity_type="bank_payment",
            company="cacao",
            prefix_template="PAG-*YYYY*-",
        )
        contador = ExternalCounter(
            company="cacao",
            name=f"Chequera {sufijo}",
            counter_type="checkbook",
            naming_series_id=actual.id,
        )
        database.session.add_all([actual, nueva, contador])
        database.session.flush()
        database.session.add_all(
            [
                SeriesExternalCounterMap(
                    naming_series_id=actual.id,
                    external_counter_id=contador.id,
                    priority=0,
                    condition_json='{"bank_account_id": "BANK-1"}',
                ),
                SeriesExternalCounterMap(
                    naming_series_id=actual.id,
                    external_counter_id=contador.id,
                    priority=1,
                    condition_json='{"bank_account_id": "BANK-2"}',
                ),
            ]
        )
        database.session.commit()
        contador_id = contador.id
        nueva_id = nueva.id
        actual_id = actual.id

    try:
        with app.app_context():
            contador = database.session.get(ExternalCounter, contador_id)
            _sync_counter_naming_series_map(contador, nueva_id)
            database.session.commit()
            mapeos = (
                database.session.execute(database.select(SeriesExternalCounterMap).filter_by(external_counter_id=contador_id))
                .scalars()
                .all()
            )
            assert len(mapeos) == 2
            assert {mapeo.naming_series_id for mapeo in mapeos} == {nueva_id}
            assert {mapeo.condition_json for mapeo in mapeos} == {
                '{"bank_account_id": "BANK-1"}',
                '{"bank_account_id": "BANK-2"}',
            }

            _sync_counter_naming_series_map(contador, None)
            database.session.commit()
            assert (
                database.session.execute(database.select(SeriesExternalCounterMap).filter_by(external_counter_id=contador_id))
                .scalars()
                .all()
                == []
            )
    finally:
        with app.app_context():
            database.session.execute(
                database.delete(SeriesExternalCounterMap).where(SeriesExternalCounterMap.external_counter_id == contador_id)
            )
            database.session.execute(database.delete(ExternalCounter).where(ExternalCounter.id == contador_id))
            database.session.execute(database.delete(NamingSeries).where(NamingSeries.id.in_([nueva_id, actual_id])))
            database.session.commit()
