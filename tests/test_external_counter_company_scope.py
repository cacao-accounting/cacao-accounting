# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2331: la numeración automática solo compite con contadores de la compañía."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.database import (
    Entity,
    ExternalCounter,
    ExternalNumberUsage,
    GeneratedIdentifierLog,
    NamingSeries,
    SeriesExternalCounterMap,
    database,
)
from cacao_accounting.document_identifiers import (
    IdentifierConfigurationError,
    _ensure_series_sequence,
    _resolve_counter_from_mappings,
    assign_document_identifier,
)


@pytest.fixture
def escenario(entorno_contable_aislado):
    """Serie global con contadores propio y ajeno mapeados."""
    application = entorno_contable_aislado.app
    sufijo = uuid4().hex[:6].upper()
    with application.app_context():
        ajena = Entity(
            code="OTRA",
            company_name=f"Compañía ajena {sufijo}",
            tax_id=f"TAX-{sufijo}",
            currency="NIO",
            enabled=True,
            status="activo",
        )
        serie = NamingSeries(
            name=f"Serie global {sufijo}",
            entity_type="bank_payment",
            company=None,
            prefix_template="PAG-*YYYY*-",
            is_active=True,
        )
        propio = ExternalCounter(
            company="cacao",
            name=f"Chequera propia {sufijo}",
            counter_type="checkbook",
            prefix="PROP-",
            last_used=0,
            is_active=True,
            naming_series_id=None,
        )
        ajeno = ExternalCounter(
            company="OTRA",
            name=f"Chequera ajena {sufijo}",
            counter_type="checkbook",
            prefix="AJEN-",
            last_used=0,
            is_active=True,
            naming_series_id=None,
        )
        database.session.add_all([ajena, serie, propio, ajeno])
        database.session.flush()
        _ensure_series_sequence(serie)
        database.session.add_all(
            [
                SeriesExternalCounterMap(
                    naming_series_id=serie.id,
                    external_counter_id=ajeno.id,
                    priority=0,
                    condition_json='{"payment_method": "check"}',
                ),
                SeriesExternalCounterMap(
                    naming_series_id=serie.id,
                    external_counter_id=propio.id,
                    priority=5,
                    condition_json=None,
                ),
            ]
        )
        database.session.commit()
        return SimpleNamespace(
            application=application,
            serie_id=serie.id,
            propio_id=propio.id,
            ajeno_id=ajeno.id,
        )


def _contador(escenario, counter_id: str) -> ExternalCounter:
    """Recarga un contador dentro del contexto activo."""
    return database.session.get(ExternalCounter, counter_id)


def test_mapeo_ajeno_mas_prioritario_no_desplaza_al_propio(escenario):
    """El fallback propio se elige aunque la regla ajena tenga mejor prioridad."""
    with escenario.application.app_context():
        elegido = _resolve_counter_from_mappings(escenario.serie_id, {"payment_method": "check"}, "cacao")

        assert elegido is not None
        assert elegido.company == "cacao"
        assert elegido.id == escenario.propio_id


def test_mapeo_ajeno_condicional_no_compite_con_el_propio(escenario):
    """Un contador ajeno con condición coincidente no entra en el ranking."""
    with escenario.application.app_context():
        elegido = _resolve_counter_from_mappings(escenario.serie_id, {"payment_method": "check"}, "cacao")
        ajeno = _contador(escenario, escenario.ajeno_id)

        assert elegido.id != ajeno.id
        assert ajeno.last_used == 0


def test_sin_contador_elegible_la_serie_no_usa_contador_ajeno(escenario):
    """Sin contador propio la resolución automática no devuelve el ajeno."""
    with escenario.application.app_context():
        propio = _contador(escenario, escenario.propio_id)
        database.session.delete(propio)
        database.session.commit()

        assert _resolve_counter_from_mappings(escenario.serie_id, {"payment_method": "check"}, "cacao") is None


def test_condiciones_propias_conservan_precedencia(escenario):
    """Entre contadores propios gana el que coincide con más condiciones."""
    with escenario.application.app_context():
        especifico = ExternalCounter(
            company="cacao",
            name="Chequera específica",
            counter_type="checkbook",
            prefix="ESP-",
            last_used=0,
            is_active=True,
        )
        database.session.add(especifico)
        database.session.flush()
        database.session.add(
            SeriesExternalCounterMap(
                naming_series_id=escenario.serie_id,
                external_counter_id=especifico.id,
                priority=9,
                condition_json='{"payment_method": "check", "bank_account_id": "BANCO-1"}',
            )
        )
        database.session.commit()

        elegido = _resolve_counter_from_mappings(
            escenario.serie_id,
            {"payment_method": "check", "bank_account_id": "BANCO-1"},
            "cacao",
        )

        assert elegido is not None
        assert elegido.id == especifico.id


def test_asignacion_automatica_usa_el_contador_propio(escenario):
    """La numeración se completa con el contador propio y no consume el ajeno."""
    with escenario.application.app_context():
        documento = SimpleNamespace(
            id=str(uuid4()),
            company="cacao",
            document_no="",
            posting_date=None,
            naming_series_id=None,
            external_counter_id=None,
            external_number=None,
        )
        try:
            assign_document_identifier(
                document=documento,
                entity_type="bank_payment",
                posting_date_raw=date(2026, 5, 15),
                naming_series_id=escenario.serie_id,
                external_context={"payment_method": "check"},
            )
            database.session.commit()

            propio = _contador(escenario, escenario.propio_id)
            ajeno = _contador(escenario, escenario.ajeno_id)
            assert documento.document_no
            assert documento.external_counter_id == propio.id
            assert documento.external_number == "PROP-00001"
            assert propio.last_used == 1
            assert ajeno.last_used == 0
            assert (
                database.session.execute(
                    database.select(ExternalNumberUsage).filter_by(external_counter_id=ajeno.id)
                ).scalar_one_or_none()
                is None
            )
        finally:
            database.session.execute(
                database.delete(GeneratedIdentifierLog).where(GeneratedIdentifierLog.entity_id == documento.id)
            )
            database.session.execute(database.delete(ExternalNumberUsage).where(ExternalNumberUsage.entity_id == documento.id))
            database.session.commit()


def test_contador_explicito_ajeno_se_rechaza_sin_numerar(escenario):
    """Un contador manual de otra compañía no asigna número ni consume series."""
    with escenario.application.app_context():
        documento = SimpleNamespace(
            id=str(uuid4()),
            company="cacao",
            document_no="",
            posting_date=None,
            naming_series_id=None,
            external_counter_id=None,
            external_number=None,
        )
        with pytest.raises(IdentifierConfigurationError):
            assign_document_identifier(
                document=documento,
                entity_type="bank_payment",
                posting_date_raw=date(2026, 5, 15),
                naming_series_id=escenario.serie_id,
                external_counter_id=escenario.ajeno_id,
            )

        assert documento.document_no == ""
        assert documento.naming_series_id is None
        assert _contador(escenario, escenario.ajeno_id).last_used == 0
        assert _contador(escenario, escenario.propio_id).last_used == 0
        assert (
            database.session.execute(
                database.select(GeneratedIdentifierLog).filter_by(entity_id=documento.id)
            ).scalar_one_or_none()
            is None
        )
        assert (
            database.session.execute(
                database.select(ExternalNumberUsage).filter_by(entity_id=documento.id)
            ).scalar_one_or_none()
            is None
        )
