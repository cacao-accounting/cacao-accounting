# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1580: el número externo debe respetar el prefijo del contador."""

from __future__ import annotations

import pytest

from cacao_accounting.database import ExternalCounter, ExternalNumberUsage, database
from cacao_accounting.document_identifiers import (
    IdentifierConfigurationError,
    _validate_and_register_external_number,
)


@pytest.fixture
def contador_con_prefijo(app):
    with app.app_context():
        contador = ExternalCounter(
            company="cacao",
            name="Chequera 1580",
            counter_type="checkbook",
            prefix="CHK-",
            padding=5,
            last_used=0,
            is_active=True,
        )
        database.session.add(contador)
        database.session.commit()
        contador_id = contador.id
    yield app, contador_id
    with app.app_context():
        database.session.execute(
            database.delete(ExternalNumberUsage).where(ExternalNumberUsage.external_counter_id == contador_id)
        )
        database.session.execute(database.delete(ExternalCounter).where(ExternalCounter.id == contador_id))
        database.session.commit()


def test_numero_sin_prefijo_se_rechaza_sin_avanzar_el_contador(contador_con_prefijo):
    """'00042' no se interpreta como secuencia 42 ni modifica last_used."""
    application, contador_id = contador_con_prefijo
    with application.app_context():
        contador = database.session.get(ExternalCounter, contador_id)
        with pytest.raises(IdentifierConfigurationError, match="prefijo"):
            _validate_and_register_external_number(
                counter=contador,
                external_number="00042",
                entity_type="payment_entry",
                entity_id="p1",
            )
        assert contador.last_used == 0
        usos = (
            database.session.execute(database.select(ExternalNumberUsage).filter_by(external_counter_id=contador_id))
            .scalars()
            .all()
        )
        assert usos == []


def test_numero_con_prefijo_registra_la_secuencia(contador_con_prefijo):
    """'CHK-00042' registra 42 y actualiza la sugerencia siguiente."""
    application, contador_id = contador_con_prefijo
    with application.app_context():
        contador = database.session.get(ExternalCounter, contador_id)
        _validate_and_register_external_number(
            counter=contador,
            external_number="CHK-00042",
            entity_type="payment_entry",
            entity_id="p1",
        )
        database.session.commit()
        uso = database.session.execute(
            database.select(ExternalNumberUsage).filter_by(external_counter_id=contador_id)
        ).scalar_one()
        assert uso.sequence_value == 42
        assert contador.last_used == 42
        assert contador.next_suggested_formatted == "CHK-00043"
