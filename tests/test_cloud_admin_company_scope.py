# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1828: la clasificación admin no evade el aislamiento por compañía en Cloud.

Las listas documentales y el listado de proveedores deben aplicar el mismo
alcance: solo compañías otorgadas explícitamente en `UserCompanyAccess`.
Desktop conserva el bypass de administrador porque opera con una sola base.
"""

from __future__ import annotations

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
    PurchaseOrder,
    User,
    UserCompanyAccess,
    database,
)

LISTA_OC = "/buying/purchase-order/list"
LISTA_PROVEEDORES = "/buying/supplier/list"


@pytest.fixture
def escenario_admin_cloud():
    """Dos compañías con datos similares y un administrador sin asignaciones."""
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
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="purchases", default=True, enabled=True),
                Entity(code="alpha", name="Alpha", company_name="Alpha SA", tax_id="A-1", currency="NIO", enabled=True),
                Entity(code="beta", name="Beta", company_name="Beta SA", tax_id="B-1", currency="NIO", enabled=True),
            ]
        )
        database.session.flush()
        admin = User(
            id=f"admin-{suffix}",
            user=f"admin_{suffix}",
            name="Admin Cloud",
            password=b"unused",
            classification="admin",
            active=True,
        )
        proveedor_alpha = Party(code=f"PA-{suffix}", name="Proveedor Alpha", is_supplier=True, is_active=True)
        proveedor_beta = Party(code=f"PB-{suffix}", name="Proveedor Beta", is_supplier=True, is_active=True)
        database.session.add_all([admin, proveedor_alpha, proveedor_beta])
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="alpha", party_id=proveedor_alpha.id, is_active=True),
                CompanyParty(company="beta", party_id=proveedor_beta.id, is_active=True),
            ]
        )
        orden_alpha = PurchaseOrder(
            company="alpha",
            document_no=f"OC-A-{suffix}",
            supplier_id=proveedor_alpha.id,
            supplier_name=proveedor_alpha.name,
            posting_date=date(2026, 5, 10),
            docstatus=1,
            transaction_currency="NIO",
        )
        orden_beta = PurchaseOrder(
            company="beta",
            document_no=f"OC-B-{suffix}",
            supplier_id=proveedor_beta.id,
            supplier_name=proveedor_beta.name,
            posting_date=date(2026, 5, 10),
            docstatus=1,
            transaction_currency="NIO",
        )
        database.session.add_all([orden_alpha, orden_beta])
        database.session.commit()
        ids = {"admin": admin.id, "suffix": suffix}
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


def _grant_alpha(application, user_id: str) -> None:
    """Otorga explícitamente Alpha al administrador."""
    with application.app_context():
        database.session.add(UserCompanyAccess(user_id=user_id, company_code="alpha"))
        database.session.commit()


def test_admin_sin_asignaciones_no_ve_companias(escenario_admin_cloud):
    """Sin UserCompanyAccess, admin no ve documentos ni proveedores."""
    application, ids = escenario_admin_cloud
    client = _login(application, ids["admin"])
    suffix = ids["suffix"]

    ordenes = client.get(LISTA_OC).get_data(as_text=True)
    proveedores = client.get(LISTA_PROVEEDORES).get_data(as_text=True)

    assert f"OC-A-{suffix}" not in ordenes and f"OC-B-{suffix}" not in ordenes
    assert "Proveedor Alpha" not in proveedores and "Proveedor Beta" not in proveedores


def test_admin_con_asignacion_ve_solo_esa_compania(escenario_admin_cloud):
    """La asignación explícita limita ambas listas a Alpha."""
    application, ids = escenario_admin_cloud
    _grant_alpha(application, ids["admin"])
    client = _login(application, ids["admin"])
    suffix = ids["suffix"]

    ordenes = client.get(LISTA_OC).get_data(as_text=True)
    proveedores = client.get(LISTA_PROVEEDORES).get_data(as_text=True)

    assert f"OC-A-{suffix}" in ordenes and f"OC-B-{suffix}" not in ordenes
    assert "Proveedor Alpha" in proveedores and "Proveedor Beta" not in proveedores


def test_admin_no_consulta_compania_no_asignada_con_parametro(escenario_admin_cloud):
    """El parámetro ?company= no evade el aislamiento."""
    application, ids = escenario_admin_cloud
    _grant_alpha(application, ids["admin"])
    client = _login(application, ids["admin"])

    assert client.get(f"{LISTA_OC}?company=beta").status_code == 403
    assert client.get(f"{LISTA_PROVEEDORES}?company=beta").status_code == 403
    assert client.get(f"{LISTA_OC}?company=alpha").status_code == 200
