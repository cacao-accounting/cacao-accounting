# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1922: el reset mensual exige tokens de mes y año en el prefijo.

Sin ambos tokens, documentos de meses o años distintos pueden resolver el mismo
prefijo y chocar con la bitácora única. La configuración inválida se rechaza
antes de modificar series o secuencias.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from flask import Flask
from flask.testing import FlaskClient

from cacao_accounting.database import (
    GeneratedIdentifierLog,
    NamingSeries,
    Sequence,
    SequencePeriodCounter,
    SeriesSequenceMap,
    database,
)
from cacao_accounting.database.helpers import generate_identifier

MENSAJE_MES = "requiere que el prefijo incluya un token de mes"
MENSAJE_ANIO = "y uno de año"


def _payload(nombre: str, prefijo: str, politica: str = "monthly") -> dict[str, str]:
    """Construye el formulario HTTP de una serie mensual."""
    return {
        "nombre": nombre,
        "entity_type": "journal_entry",
        "company": "cacao",
        "prefix_template": prefijo,
        "current_value": "0",
        "increment": "1",
        "padding": "5",
        "reset_policy": politica,
        "is_active": "on",
    }


def _obtener_ids(app: Flask, nombre: str) -> tuple[str, str]:
    """Devuelve los identificadores de una serie y su secuencia asociada."""
    with app.app_context():
        serie = database.session.execute(database.select(NamingSeries).filter_by(name=nombre)).scalar_one()
        sequence_id = database.session.execute(
            database.select(SeriesSequenceMap.sequence_id).filter_by(naming_series_id=serie.id)
        ).scalar_one()
        return serie.id, sequence_id


def _crear_serie(client: FlaskClient, nombre: str, prefijo: str) -> None:
    """Crea una serie válida mediante HTTP y verifica la redirección."""
    respuesta = client.post("/accounting/naming-series/new", data=_payload(nombre, prefijo))
    assert respuesta.status_code == 302


def _limpiar(app: Flask, nombre: str) -> None:
    """Elimina una serie de prueba y sus dependencias de numeración."""
    with app.app_context():
        serie = database.session.execute(database.select(NamingSeries).filter_by(name=nombre)).scalar_one_or_none()
        if serie is None:
            return
        sequence_ids = (
            database.session.execute(database.select(SeriesSequenceMap.sequence_id).filter_by(naming_series_id=serie.id))
            .scalars()
            .all()
        )
        database.session.execute(database.delete(SeriesSequenceMap).where(SeriesSequenceMap.naming_series_id == serie.id))
        if sequence_ids:
            database.session.execute(
                database.delete(GeneratedIdentifierLog).where(GeneratedIdentifierLog.sequence_id.in_(sequence_ids))
            )
            database.session.execute(
                database.delete(SequencePeriodCounter).where(SequencePeriodCounter.sequence_id.in_(sequence_ids))
            )
            database.session.execute(database.delete(Sequence).where(Sequence.id.in_(sequence_ids)))
        database.session.delete(serie)
        database.session.commit()


def _assert_mensaje_validacion(respuesta) -> None:
    """Verifica que el formulario explique que faltan tokens de mes y año."""
    html = respuesta.get_data(as_text=True)
    assert MENSAJE_MES in html
    assert MENSAJE_ANIO in html


@pytest.mark.parametrize("prefijo", ["INV-*MM*-", "INV-*YYYY*-"])
def test_rechaza_reset_mensual_incompleto_en_alta(app, authenticated_client, prefijo):
    """Una política mensual no acepta solo mes o solo año al crear la serie."""
    nombre = f"Serie inválida {uuid4().hex[:6]}"

    respuesta = authenticated_client("admin").post(
        "/accounting/naming-series/new",
        data=_payload(nombre, prefijo),
    )

    assert respuesta.status_code == 200
    _assert_mensaje_validacion(respuesta)
    with app.app_context():
        assert database.session.execute(database.select(NamingSeries).filter_by(name=nombre)).scalar_one_or_none() is None
        assert (
            database.session.execute(database.select(Sequence).filter_by(name=f"{nombre} sequence")).scalar_one_or_none()
            is None
        )


@pytest.mark.parametrize("prefijo", ["INV-*YYYY*-*MM*-", "INV-*YY*-*MMM*-"])
def test_acepta_reset_mensual_con_token_de_mes_y_anio(app, authenticated_client, prefijo):
    """Alta una serie mensual con tokens de mes y año soportados."""
    nombre = f"Serie mensual {uuid4().hex[:6]}"
    try:
        _crear_serie(authenticated_client("admin"), nombre, prefijo)
        serie_id, sequence_id = _obtener_ids(app, nombre)
        with app.app_context():
            serie = database.session.get(NamingSeries, serie_id)
            secuencia = database.session.get(Sequence, sequence_id)
            assert serie is not None
            assert secuencia is not None
            assert serie.prefix_template == prefijo
            assert secuencia.reset_policy == "monthly"
    finally:
        _limpiar(app, nombre)


@pytest.mark.parametrize("prefijo_invalido", ["INV-*MM*-", "INV-*YYYY*-"])
def test_edicion_rechaza_reset_mensual_incompleto_y_conserva_valores(app, authenticated_client, prefijo_invalido):
    """Una edición inválida no modifica el prefijo ni los parámetros de secuencia."""
    nombre = f"Serie mensual {uuid4().hex[:6]}"
    prefijo_valido = "INV-*YYYY*-*MM*-"
    client = authenticated_client("admin")
    try:
        _crear_serie(client, nombre, prefijo_valido)
        serie_id, sequence_id = _obtener_ids(app, nombre)
        datos = _payload(nombre, prefijo_invalido)
        datos.update({"current_value": "99", "increment": "7", "padding": "9"})

        respuesta = client.post(f"/accounting/naming-series/{serie_id}/edit", data=datos)

        assert respuesta.status_code == 200
        _assert_mensaje_validacion(respuesta)
        with app.app_context():
            serie = database.session.get(NamingSeries, serie_id)
            secuencia = database.session.get(Sequence, sequence_id)
            assert serie is not None
            assert secuencia is not None
            assert serie.prefix_template == prefijo_valido
            assert secuencia.reset_policy == "monthly"
            assert (secuencia.current_value, secuencia.increment, secuencia.padding) == (0, 1, 5)
    finally:
        _limpiar(app, nombre)


@pytest.mark.parametrize(
    ("token_anio", "anios_esperados"),
    [
        ("*YYYY*", ("2025", "2026")),
        ("*YY*", ("25", "26")),
    ],
)
def test_genera_enero_en_dos_anios_sin_colision(app, authenticated_client, token_anio, anios_esperados):
    """El token de año produce prefijos y folios distintos para cada enero."""
    nombre = f"Serie anual {uuid4().hex[:6]}"
    try:
        _crear_serie(authenticated_client("admin"), nombre, f"INV-{token_anio}-*MM*-")
        serie_id, sequence_id = _obtener_ids(app, nombre)
        with app.app_context():
            identificadores = [
                generate_identifier(
                    entity_type="journal_entry",
                    entity_id=uuid4().hex[:26],
                    posting_date=date(anio, 1, 15),
                    company="cacao",
                    naming_series_id=serie_id,
                    sequence_id=sequence_id,
                )
                for anio in (2025, 2026)
            ]
            database.session.commit()

            assert identificadores == [
                f"INV-{anios_esperados[0]}-01-00001",
                f"INV-{anios_esperados[1]}-01-00001",
            ]
            assert identificadores[0] != identificadores[1]
            registros = (
                database.session.execute(
                    database.select(GeneratedIdentifierLog)
                    .where(GeneratedIdentifierLog.sequence_id == sequence_id)
                    .order_by(GeneratedIdentifierLog.posting_date)
                )
                .scalars()
                .all()
            )
            assert [registro.full_identifier for registro in registros] == identificadores
            assert [registro.sequence_period for registro in registros] == ["2025-01", "2026-01"]
    finally:
        _limpiar(app, nombre)
