# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2105: el detalle de recepción resuelve por alcance y conserva acciones.

La URL puede usar el id o el número documental. El número es único solo por
compañía; con acceso a una sola compañía resuelve, con numeración duplicada
entre compañías autorizadas responde 409. Las acciones `Crear` se calculan con
el id real del registro.
"""

from __future__ import annotations

import html
from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CompanyParty,
    Currency,
    Entity,
    Modules,
    Party,
    PurchaseReceipt,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.document_flow.tracing import get_create_actions


@pytest.fixture
def escenario_recepciones():
    """Dos recepciones con el mismo document_no en compañías distintas."""
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
    suffix = uuid4().hex[:6].upper()
    document_no = f"PR-DUP-{suffix}"
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="purchases", default=True, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                Entity(code="alpha", name="Alpha", company_name="Alpha SA", tax_id="A-1", currency="NIO", enabled=True),
                Entity(code="beta", name="Beta", company_name="Beta SA", tax_id="B-1", currency="NIO", enabled=True),
            ]
        )
        database.session.flush()
        modulos = {
            nombre: database.session.execute(database.select(Modules).filter_by(module=nombre)).scalar_one()
            for nombre in ("purchases", "inventory")
        }
        proveedores = {}
        recepciones = {}
        for company in ("alpha", "beta"):
            proveedor = Party(code=f"SUP-{company}-{suffix}", name=f"Proveedor {company}", is_supplier=True, is_active=True)
            database.session.add(proveedor)
            database.session.flush()
            database.session.add(CompanyParty(company=company, party_id=proveedor.id, is_active=True))
            receipt = PurchaseReceipt(
                company=company,
                document_no=document_no,
                supplier_id=proveedor.id,
                supplier_name=proveedor.name,
                posting_date=date(2026, 5, 10),
                docstatus=1,
                transaction_currency="NIO",
            )
            database.session.add(receipt)
            database.session.flush()
            proveedores[company] = proveedor.id
            recepciones[company] = receipt.id

        def crear_usuario(nombre: str, empresas: tuple[str, ...]) -> str:
            user_id = f"{nombre}-{suffix}"
            role = Roles(name=f"{nombre}-{suffix}", note=nombre)
            database.session.add_all([User(id=user_id, user=user_id, name=nombre, password=b"unused", active=True), role])
            database.session.flush()
            database.session.add(RolesUser(user_id=user_id, role_id=role.id, active=True))
            for modulo in modulos.values():
                database.session.add(RolesAccess(rol_id=role.id, module_id=modulo.id, access=True, view=True))
            for company in empresas:
                database.session.add(UserCompanyAccess(user_id=user_id, company_code=company))
            return user_id

        ids = {
            "document_no": document_no,
            "receipt_alpha": recepciones["alpha"],
            "receipt_beta": recepciones["beta"],
            "user_alpha": crear_usuario("alpha-only", ("alpha",)),
            "user_both": crear_usuario("alpha-beta", ("alpha", "beta")),
        }
        database.session.commit()
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _login(application, user_id: str):
    """Cliente autenticado."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _assert_acciones_presentes(application, receipt_id: str, pagina: str) -> None:
    """Comprueba que la página renderiza las URLs de las acciones reales."""
    with application.app_context(), application.test_request_context("/buying/purchase-receipt"):
        acciones = get_create_actions("purchase_receipt", receipt_id)
    assert acciones, "La recepción aprobada debe exponer acciones Crear."
    texto = html.unescape(pagina)
    assert any(accion["create_url"] and accion["create_url"] in texto for accion in acciones)


def test_detalle_por_id_expone_acciones(escenario_recepciones):
    """La ruta por PK usa el id real para calcular acciones."""
    application, ids = escenario_recepciones
    client = _login(application, ids["user_alpha"])

    response = client.get(f"/buying/purchase-receipt/{ids['receipt_alpha']}")

    assert response.status_code == 200
    _assert_acciones_presentes(application, ids["receipt_alpha"], response.get_data(as_text=True))


def test_detalle_por_document_no_resuelve_y_expone_acciones(escenario_recepciones):
    """Con una sola compañía autorizada, el número resuelve sin perder acciones."""
    application, ids = escenario_recepciones
    client = _login(application, ids["user_alpha"])

    response = client.get(f"/buying/purchase-receipt/{ids['document_no']}")

    assert response.status_code == 200
    _assert_acciones_presentes(application, ids["receipt_alpha"], response.get_data(as_text=True))


def test_document_no_duplicado_entre_companias_autorizadas_responde_409(escenario_recepciones):
    """Dos coincidencias autorizadas no producen 500 ni eligen una arbitraria."""
    application, ids = escenario_recepciones
    client = _login(application, ids["user_both"])

    assert client.get(f"/buying/purchase-receipt/{ids['document_no']}").status_code == 409
