"""El alta de recepción respeta el alcance de compañía del documento origen."""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    PurchaseOrder,
    PurchaseReceipt,
    User,
    UserCompanyAccess,
    Warehouse,
    database,
)


@pytest.fixture
def receipt_source_scenario():
    """Build two companies and a warehouse user authorized only for Alpha."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="inventory", default=False, enabled=True),
                Modules(module="purchases", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J-ALPHA",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name="Beta SA",
                    tax_id="J-BETA",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id="receipt_user",
                    user="receipt_user",
                    name="Bodeguero Alpha",
                    password=proteger_passwd("receipt-user-password"),
                    active=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                UserCompanyAccess(user_id="receipt_user", company_code="alpha"),
                PurchaseOrder(
                    company="alpha",
                    posting_date=date(2026, 10, 20),
                    docstatus=1,
                    document_no="PO-ALPHA",
                    supplier_name="Proveedor Alpha",
                ),
                PurchaseOrder(
                    company="beta",
                    posting_date=date(2026, 10, 20),
                    docstatus=1,
                    document_no="PO-BETA",
                    supplier_name="Proveedor Confidencial Beta",
                ),
                PurchaseReceipt(
                    company="beta",
                    posting_date=date(2026, 10, 20),
                    docstatus=1,
                    document_no="PR-BETA",
                    supplier_name="Proveedor Confidencial Beta",
                ),
                Warehouse(code="BETA-WH", name="Bodega Confidencial Beta", company="beta"),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("receipt_user", "inventory_auxiliar")
        database.session.commit()
        ids = {
            "order_alpha": database.session.query(PurchaseOrder.id).filter_by(company="alpha").scalar(),
            "order_beta": database.session.query(PurchaseOrder.id).filter_by(company="beta").scalar(),
            "receipt_beta": database.session.query(PurchaseReceipt.id).filter_by(company="beta").scalar(),
        }
    yield app, ids
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app):
    """Return an authenticated client for the Alpha-only warehouse user."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "receipt_user"
        session["_fresh"] = True
    return client


@pytest.mark.parametrize(("source_key", "query_field"), [("order_beta", "from_order"), ("receipt_beta", "from_receipt")])
def test_recepcion_no_expone_origen_de_otra_compania(receipt_source_scenario, source_key, query_field):
    """Foreign source IDs cannot reveal supplier or company data in the new form."""
    app, ids = receipt_source_scenario
    response = _authenticated_client(app).get(f"/buying/purchase-receipt/new?{query_field}={ids[source_key]}")

    assert response.status_code == 403
    body = response.get_data(as_text=True)
    assert "Proveedor Confidencial Beta" not in body
    assert "PO-BETA" not in body
    assert "PR-BETA" not in body


def test_recepcion_precarga_origen_de_compania_autorizada(receipt_source_scenario):
    """An authorized source remains available to the receipt workflow."""
    app, ids = receipt_source_scenario
    response = _authenticated_client(app).get(f"/buying/purchase-receipt/new?from_order={ids['order_alpha']}")

    assert response.status_code == 200
    assert "Proveedor Alpha" in response.get_data(as_text=True)


def test_recepcion_no_carga_catalogo_de_compania_no_autorizada(receipt_source_scenario):
    """An explicit foreign company cannot expose its warehouse catalog without a source."""
    app, _ = receipt_source_scenario
    response = _authenticated_client(app).get("/buying/purchase-receipt/new?company=beta")

    assert response.status_code == 403
    assert "Bodega Confidencial Beta" not in response.get_data(as_text=True)
