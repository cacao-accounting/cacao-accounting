# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Detalle de recepción resuelto por número documental.

Escenario de negocio: dos compañías pueden compartir el mismo ``document_no``.
El detalle debe resolver la recepción dentro de las compañías autorizadas, no
fallar con 500, y calcular las acciones ``Crear`` con el ID real del documento.
"""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Entity,
    Modules,
    PurchaseReceipt,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "recepcion-lookup-2026"
FECHA = date(2026, 10, 20)


@pytest.fixture
def recepciones_duplicadas():
    """Dos recepciones con el mismo número en compañías distintas."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="purchases", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
                UserCompanyAccess(user_id="admin", company_code="cacao"),
            ]
        )
        database.session.flush()
        propia = PurchaseReceipt(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="PR-DUP",
            supplier_name="Proveedor Cacao",
        )
        ajena = PurchaseReceipt(
            company="alpha",
            posting_date=FECHA,
            docstatus=1,
            document_no="PR-DUP",
            supplier_name="Proveedor Alpha",
        )
        database.session.add_all([propia, ajena])
        database.session.commit()
        ids = {"propia": propia.id, "ajena": ajena.id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "admin", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_detalle_por_numero_resuelve_la_compania_autorizada(recepciones_duplicadas):
    """El número duplicado no produce 500 y resuelve la recepción propia."""
    application, ids = recepciones_duplicadas
    client = application.test_client()
    _iniciar(client)

    response = client.get("/buying/purchase-receipt/PR-DUP")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Proveedor Cacao" in cuerpo
    assert "Proveedor Alpha" not in cuerpo
    assert f"from_receipt={ids['propia']}" in cuerpo


def test_detalle_por_id_conserva_las_acciones(recepciones_duplicadas):
    """Control positivo: el acceso por ID ya calcula acciones con el ID real."""
    application, ids = recepciones_duplicadas
    client = application.test_client()
    _iniciar(client)

    response = client.get(f"/buying/purchase-receipt/{ids['propia']}")

    assert response.status_code == 200
    assert f"from_receipt={ids['propia']}" in response.get_data(as_text=True)
