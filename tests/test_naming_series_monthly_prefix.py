# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1922: el reset mensual exige un prefijo con token de mes.

Guardar una serie mensual sin *MM*/*MMM* produciría el mismo identificador cada
mes y chocaría con la bitácora única; la configuración se rechaza al guardar.
"""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.database import NamingSeries, Sequence, SeriesSequenceMap, database


def _payload(nombre: str, prefijo: str, politica: str = "monthly") -> dict[str, str]:
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


def _limpiar(app, nombre: str) -> None:
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
        database.session.delete(serie)
        if sequence_ids:
            database.session.execute(database.delete(Sequence).where(Sequence.id.in_(sequence_ids)))
        database.session.commit()


def test_rechaza_reset_mensual_sin_token_de_mes(app, authenticated_client, entorno_contable):
    """La combinación INV- + monthly no se persiste."""
    del entorno_contable
    nombre = f"Serie inválida {uuid4().hex[:6]}"

    response = authenticated_client("admin").post(
        "/accounting/naming-series/new",
        data=_payload(nombre, "INV-"),
    )

    assert response.status_code == 200
    assert "requiere que el prefijo incluya *MM* o *MMM*" in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.execute(database.select(NamingSeries).filter_by(name=nombre)).scalar_one_or_none() is None


def test_acepta_reset_mensual_con_token_de_mes_y_lo_conserva_al_editar(app, authenticated_client, entorno_contable):
    """Con *MM* la serie se crea; editar a un prefijo sin mes se rechaza."""
    del entorno_contable
    nombre = f"Serie mensual {uuid4().hex[:6]}"
    client = authenticated_client("admin")
    try:
        creada = client.post("/accounting/naming-series/new", data=_payload(nombre, "INV-*MM*-"))
        assert creada.status_code == 302
        with app.app_context():
            serie = database.session.execute(database.select(NamingSeries).filter_by(name=nombre)).scalar_one()
            serie_id = serie.id
            assert serie.prefix_template == "INV-*MM*-"

        editada = client.post(
            f"/accounting/naming-series/{serie_id}/edit",
            data=_payload(nombre, "INV-"),
        )
        assert editada.status_code == 200
        assert "requiere que el prefijo incluya *MM* o *MMM*" in editada.get_data(as_text=True)
        with app.app_context():
            assert database.session.get(NamingSeries, serie_id).prefix_template == "INV-*MM*-"
    finally:
        _limpiar(app, nombre)
