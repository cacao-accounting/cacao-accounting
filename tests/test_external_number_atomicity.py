# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2332: un rechazo de numeración externa no deja identidad ni consumo parcial."""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace

import pytest

import cacao_accounting.document_identifiers as document_identifiers
from cacao_accounting.database import (
    ExternalCounter,
    ExternalNumberUsage,
    GeneratedIdentifierLog,
    NamingSeries,
    database,
)
from cacao_accounting.document_identifiers import (
    ExternalNumberDuplicateError,
    IdentifierConfigurationError,
    _ensure_series_sequence,
    assign_document_identifier,
)

FECHA = date(2026, 5, 15)


@pytest.fixture
def escenario(entorno_contable_aislado):
    """Serie con secuencia y contador de la compañía del documento."""
    application = entorno_contable_aislado.app
    with application.app_context():
        serie = NamingSeries(
            name="Serie atómica",
            entity_type="bank_payment",
            company="cacao",
            prefix_template="PAG-*YYYY*-",
            is_active=True,
            is_default=True,
        )
        contador = ExternalCounter(
            company="cacao",
            name="Chequera atómica",
            counter_type="checkbook",
            prefix="CHK-",
            padding=5,
            last_used=0,
            is_active=True,
        )
        database.session.add_all([serie, contador])
        database.session.flush()
        _ensure_series_sequence(serie)
        database.session.commit()
        return SimpleNamespace(application=application, serie_id=serie.id, contador_id=contador.id)


def _documento() -> SimpleNamespace:
    """Documento mínimo con los campos que asigna la numeración."""
    return SimpleNamespace(
        id=str(uuid.uuid4()),
        company="cacao",
        document_no="",
        posting_date=None,
        naming_series_id=None,
        external_counter_id=None,
        external_number=None,
    )


def _asignar(escenario, documento, **kwargs) -> None:
    """Invoca la asignación con la serie del escenario."""
    assign_document_identifier(
        document=documento,
        entity_type="bank_payment",
        posting_date_raw=FECHA,
        naming_series_id=escenario.serie_id,
        **kwargs,
    )


def _registros(documento) -> tuple[object | None, object | None]:
    """Devuelve el log de identificador y el uso externo del documento."""
    log = database.session.execute(
        database.select(GeneratedIdentifierLog).filter_by(entity_id=documento.id)
    ).scalar_one_or_none()
    uso = database.session.execute(database.select(ExternalNumberUsage).filter_by(entity_id=documento.id)).scalar_one_or_none()
    return log, uso


def test_prefijo_invalido_no_consume_serie_y_permite_reintentar(escenario):
    """El prefijo inválido se rechaza antes de generar el número interno."""
    with escenario.application.app_context():
        contador = database.session.get(ExternalCounter, escenario.contador_id)
        documento = _documento()
        with pytest.raises(IdentifierConfigurationError, match="prefijo"):
            _asignar(escenario, documento, external_counter_id=escenario.contador_id, external_number="00042")

        log, uso = _registros(documento)
        assert documento.document_no == ""
        assert documento.external_number is None
        assert contador.last_used == 0
        assert (log, uso) == (None, None)

        # El contrato público permite al llamador continuar tras el rechazo.
        _asignar(escenario, documento, external_counter_id=escenario.contador_id, external_number="CHK-00001")
        database.session.commit()

        log, uso = _registros(documento)
        assert documento.document_no.endswith("00001")
        assert documento.external_number == "CHK-00001"
        assert documento.external_counter_id == escenario.contador_id
        assert log is not None
        assert uso is not None and uso.sequence_value == 1
        assert contador.last_used == 1


def test_duplicado_conocido_no_consume_serie_y_permite_reintentar(escenario):
    """Un número ya registrado se rechaza sin gastar el consecutivo interno."""
    with escenario.application.app_context():
        contador = database.session.get(ExternalCounter, escenario.contador_id)
        database.session.add(
            ExternalNumberUsage(
                external_counter_id=contador.id,
                external_number="CHK-00001",
                entity_type="bank_payment",
                entity_id="documento-previo",
                sequence_value=1,
            )
        )
        contador.last_used = 1
        database.session.commit()

        documento = _documento()
        with pytest.raises(ExternalNumberDuplicateError):
            _asignar(escenario, documento, external_counter_id=escenario.contador_id, external_number="CHK-00001")

        log, uso = _registros(documento)
        assert documento.document_no == ""
        assert log is None and uso is None

        _asignar(escenario, documento, external_counter_id=escenario.contador_id, external_number="CHK-00002")
        database.session.commit()

        assert documento.document_no.endswith("00001")
        assert documento.external_number == "CHK-00002"
        assert contador.last_used == 2


def test_colision_concurrente_revierte_serie_y_sesion(escenario, monkeypatch):
    """Una carrera de unicidad revierte la secuencia y deja la sesión utilizable."""
    with escenario.application.app_context():
        contador = database.session.get(ExternalCounter, escenario.contador_id)
        database.session.add(
            ExternalNumberUsage(
                external_counter_id=contador.id,
                external_number="CHK-00001",
                entity_type="bank_payment",
                entity_id="documento-concurrente",
                sequence_value=1,
            )
        )
        contador.last_used = 1
        database.session.commit()

        # Simula que la validación previa no vio el registro agregado por otro
        # proceso después de comprobar duplicados.
        monkeypatch.setattr(document_identifiers, "_validate_external_number", lambda *args, **kwargs: None)

        documento = _documento()
        with pytest.raises(ExternalNumberDuplicateError):
            _asignar(escenario, documento, external_counter_id=escenario.contador_id, external_number="CHK-00001")

        log, uso = _registros(documento)
        assert documento.document_no == ""
        assert documento.external_number is None
        assert log is None and uso is None
        assert contador.last_used == 1

        monkeypatch.undo()
        _asignar(escenario, documento, external_counter_id=escenario.contador_id, external_number="CHK-00009")
        database.session.commit()

        assert documento.document_no.endswith("00001")
        assert documento.external_number == "CHK-00009"
        assert contador.last_used == 9


def test_operacion_valida_confirma_documento_uso_y_contador(escenario):
    """El camino exitoso confirma documento, uso externo y último número usado."""
    with escenario.application.app_context():
        contador = database.session.get(ExternalCounter, escenario.contador_id)
        documento = _documento()
        _asignar(escenario, documento, external_counter_id=escenario.contador_id, external_number="CHK-00007")
        database.session.commit()

        log, uso = _registros(documento)
        assert documento.document_no.endswith("00001")
        assert documento.external_number == "CHK-00007"
        assert log is not None
        assert uso is not None and uso.sequence_value == 7
        assert contador.last_used == 7
        assert contador.next_suggested_formatted == "CHK-00008"
