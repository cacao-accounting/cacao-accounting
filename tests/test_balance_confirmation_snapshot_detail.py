# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El detalle de confirmación tolera snapshots ausentes o inválidos.

Escenario de negocio (issue #2109): con ``snapshot_json`` NULL el handler
dejaba ``{}`` y la plantilla leía ``snapshot["items"]``, que resolvía al
método ``dict.items`` y lanzaba TypeError (HTTP 500).
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    BalanceConfirmation,
    Currency,
    Entity,
    Modules,
    Party,
    User,
    database,
)

FECHA = date(2026, 10, 15)


def _crear_app(snapshot_json: str | None):
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
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        cliente = Party(code="CLI-1", name="Cliente", is_customer=True)
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
                    password=proteger_passwd("AdminPass!123"),
                    active=True,
                    classification="admin",
                    company="cacao",
                ),
                cliente,
            ]
        )
        database.session.flush()
        confirmacion = BalanceConfirmation(
            company="cacao",
            document_no="BC-EMPTY",
            party_type="customer",
            party_id=cliente.id,
            cutoff_date=FECHA,
            status="draft",
            snapshot_json=snapshot_json,
        )
        database.session.add(confirmacion)
        database.session.commit()
        return application, confirmacion.id


@pytest.mark.parametrize("snapshot_json", [None, "", "{}", "{", '{"items": null, "totals": null}'])
def test_el_detalle_renderiza_sin_snapshot_valido(snapshot_json):
    """Un snapshot ausente, vacío, malformado o con nulos responde 200."""
    application, confirmation_id = _crear_app(snapshot_json)
    try:
        client = application.test_client()
        login = client.post(
            "/login",
            data={"usuario": "admin", "acceso": "AdminPass!123"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        respuesta = client.get(f"/accounting/balance-confirmations/{confirmation_id}")

        assert respuesta.status_code == 200
        assert "El snapshot no contiene partidas abiertas." in respuesta.get_data(as_text=True)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
