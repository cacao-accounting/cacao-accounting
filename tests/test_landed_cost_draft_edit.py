# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1752: editar un costo de importación actualiza el mismo borrador.

El enlace "Editar" apuntaba a la ruta de alta y un POST creaba otro documento.
La ruta `/import-landed-cost/<id>/edit` debe cargar el borrador, actualizarlo
en sitio (sin duplicar) y rechazar la edición de documentos aprobados.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.compras import services as compras_services
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    ImportLandedCost,
    ImportLandedCostCharge,
    ImportLandedCostItem,
    Party,
    PurchaseInvoice,
    Item,
    Modules,
    UOM,
    Roles,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

FECHA = date(2026, 5, 15)


@pytest.fixture
def landed_cost_edit_scenario():
    """Compañía con un costo de importación en borrador y sus líneas."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="purchases", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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
                    name="Admin",
                    password=b"x",
                    classification="admin",
                    active=True,
                    company="cacao",
                ),
                UOM(code="UND", name="Unidad", is_active=True),
            ]
        )
        database.session.flush()
        database.session.add(
            Item(
                code="ART01",
                name="Articulo importado",
                item_type="goods",
                is_stock_item=True,
                is_purchase_item=True,
                is_sale_item=True,
                default_uom="UND",
            )
        )
        database.session.add(UserCompanyAccess(user_id="admin", company_code="cacao"))
        rol = Roles(name="admin", note="admin")
        database.session.add(rol)
        database.session.flush()
        database.session.add(RolesUser(user_id="admin", role_id=rol.id, active=True))
        database.session.flush()
        proveedor = Party(code="PRV01", name="Proveedor import", is_supplier=True, is_active=True)
        database.session.add(proveedor)
        database.session.flush()
        factura = PurchaseInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="CMP-1752",
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
        )
        database.session.add(factura)
        database.session.flush()
        registro = ImportLandedCost(
            company="cacao",
            posting_date=FECHA,
            document_date=FECHA,
            document_type="import_landed_cost",
            allocation_method="by_value",
            purchase_invoice_id=factura.id,
            supplier_id=proveedor.id,
            supplier_name="Proveedor import",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            docstatus=0,
        )
        database.session.add(registro)
        database.session.flush()
        database.session.add(
            ImportLandedCostItem(
                import_landed_cost_id=registro.id,
                item_code="ART01",
                item_name="Articulo importado",
                qty=Decimal("1"),
                uom="UND",
                rate=Decimal("100"),
                amount=Decimal("100"),
                base_amount=Decimal("100"),
            )
        )
        database.session.add(
            ImportLandedCostCharge(
                import_landed_cost_id=registro.id,
                concept="Flete",
                amount=Decimal("10"),
                charge_type="charge",
            )
        )
        database.session.commit()
        landed_id = registro.id
    yield app, {"landed": landed_id}
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _client(application):
    from flask_login import login_user

    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    with application.app_context():
        login_user(database.session.get(User, "admin"))
    return client


def test_edicion_actualiza_el_mismo_documento_sin_duplicar(landed_cost_edit_scenario, monkeypatch):
    """El POST de edición no crea otro documento y conserva la identidad."""
    application, ids = landed_cost_edit_scenario
    monkeypatch.setattr(compras_services, "exige_acceso_compania", lambda *_a, **_k: None)
    form = {
        "company": "cacao",
        "posting_date": FECHA.isoformat(),
        "allocation_method": "by_quantity",
        "remarks": "Editado",
        "item_item_code_0": "ART01",
        "item_item_name_0": "Articulo importado",
        "item_qty_0": "1",
        "item_uom_0": "UND",
        "item_rate_0": "100",
        "item_amount_0": "100",
        "charge_concept_0": "Flete",
        "charge_type_0": "charge",
        "charge_amount_0": "15",
    }
    with application.test_request_context(f"/buying/import-landed-cost/{ids['landed']}/edit", method="POST", data=form):
        registro = database.session.get(ImportLandedCost, ids["landed"])
        response = compras_services._update_import_landed_cost_from_request(registro)

    assert response is not None
    with application.app_context():
        documentos = database.session.execute(database.select(ImportLandedCost)).scalars().all()
        assert len(documentos) == 1
        actualizado = documentos[0]
        assert actualizado.id == ids["landed"]
        assert actualizado.allocation_method == "by_quantity"
        assert actualizado.remarks == "Editado"


def test_edicion_rechaza_documento_aprobado(landed_cost_edit_scenario, monkeypatch):
    """Un documento aprobado no se edita."""
    application, ids = landed_cost_edit_scenario
    monkeypatch.setattr(compras_services, "exige_acceso_compania", lambda *_a, **_k: None)
    with application.app_context():
        registro = database.session.get(ImportLandedCost, ids["landed"])
        registro.docstatus = 1
        database.session.commit()

    form = {"company": "cacao", "posting_date": FECHA.isoformat(), "allocation_method": "by_value"}
    with application.test_request_context(f"/buying/import-landed-cost/{ids['landed']}/edit", method="POST", data=form):
        registro = database.session.get(ImportLandedCost, ids["landed"])
        response = compras_services._update_import_landed_cost_from_request(registro)

    assert response is None
    with application.app_context():
        assert database.session.get(ImportLandedCost, ids["landed"]).docstatus == 1
