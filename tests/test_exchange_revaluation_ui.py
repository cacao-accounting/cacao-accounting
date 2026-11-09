# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La UI de revalorización filtra por estado real y muestra moneda.

Escenario de negocio (issue #2134): el filtro ofrecía estados de ``docstatus``
que no representan ``posted``/``voided``; el listado impresión códigos crudos
y los totales omitían la moneda persistida en la corrida.
"""

from __future__ import annotations

import gettext
from datetime import date

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, ExchangeRevaluation, Modules, User, database

FECHA = date(2026, 10, 15)


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        publicado = ExchangeRevaluation(
            company="cacao",
            status="posted",
            docstatus=1,
            run_date=FECHA,
            month=10,
            year=2026,
            currency="NIO",
            total_gain=12.5,
            total_loss=0,
            document_no="REV-1",
        )
        anulado = ExchangeRevaluation(
            company="cacao",
            status="voided",
            docstatus=1,
            run_date=FECHA,
            month=10,
            year=2026,
            currency="NIO",
            total_gain=0,
            total_loss=3,
            document_no="REV-2",
        )
        database.session.add_all([publicado, anulado])
        database.session.commit()
        ids = {"posted": publicado.id, "voided": anulado.id}
    return application, ids


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _html(client, ruta: str) -> str:
    respuesta = client.get(ruta)
    assert respuesta.status_code == 200
    return respuesta.get_data(as_text=True)


def test_el_filtro_de_estado_usa_los_codigos_reales():
    """posted y voided acotan la lista; ya no devuelven las mismas filas."""
    application, _ = _crear_app()
    try:
        client = _cliente(application)

        todos = _html(client, "/accounting/exchange-revaluation")
        posted = _html(client, "/accounting/exchange-revaluation?status=posted")
        voided = _html(client, "/accounting/exchange-revaluation?status=voided")

        assert "REV-1" in todos and "REV-2" in todos
        assert "REV-1" in posted and "REV-2" not in posted
        assert "REV-2" in voided and "REV-1" not in voided
        assert 'value="posted"' in todos
        assert 'value="voided"' in todos
        assert 'value="completed_no_changes"' in todos
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_listado_y_detalle_traducen_estado_y_moneda():
    """Los códigos se muestran con etiqueta y los totales incluyen la moneda."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        listado = _html(client, "/accounting/exchange-revaluation")
        detalle = _html(client, f"/accounting/exchange-revaluation/{ids['posted']}")

        assert "Contabilizado" in listado
        assert "Anulado" in listado
        assert "NIO 12.50" in listado
        assert "NIO 3.00" in listado
        assert "Contabilizado" in detalle
        assert "NIO 12.50" in detalle
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_las_traducciones_corregidas_estan_compiladas():
    """Compañía/Periodo ya no traducen a Companies/Permission."""
    with open(
        "cacao_accounting/translations/en/LC_MESSAGES/messages.mo",
        "rb",
    ) as archivo:
        traducciones = gettext.GNUTranslations(archivo)

    assert traducciones.gettext("Compañía") == "Company"
    assert traducciones.gettext("Periodo") == "Period"
    assert traducciones.gettext("Sin cambios") == "No changes"
