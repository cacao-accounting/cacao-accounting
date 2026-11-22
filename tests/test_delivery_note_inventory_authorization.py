# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2052: Inventario es responsable de crear remisiones.

La decisión aprobada establece que ``inventory.crear`` habilita el CTA, el
formulario y el POST de una remisión sin exigir ``sales.crear``. Ventas
conserva la orden y los datos comerciales: un usuario exclusivo de Inventario
que parte de una orden aprobada solo recibe los datos logísticos.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import (
    AuditTrail,
    CompanyParty,
    DeliveryNote,
    ItemPrice,
    Modules,
    Party,
    PriceList,
    Roles,
    RolesAccess,
    RolesUser,
    SalesOrder,
    User,
    UserCompanyAccess,
    database,
)

RUTA_ALTA = "/sales/delivery-note/new"
RUTA_LISTA = "/sales/delivery-note/list"


def _modulo_id(module: str) -> str:
    """Devuelve el id del módulo ya sembrado en la app de pruebas."""
    return database.session.execute(database.select(Modules.id).filter_by(module=module)).scalar_one()


def _crear_usuario(nombre: str, role_name: str, permisos: dict[str, bool], company: str) -> str:
    """Crea un usuario con un rol de módulo único y acceso a una compañía."""
    user_id = f"{nombre}-{uuid4().hex[:8]}"
    user = User(id=user_id, user=user_id, name=nombre, password=b"unused", active=True, company=company)
    role = Roles(name=f"{role_name}-{uuid4().hex[:8]}", note=role_name)
    database.session.add_all([user, role])
    database.session.flush()
    database.session.add(RolesAccess(rol_id=role.id, module_id=_modulo_id(role_name.split("-")[0]), **permisos))
    database.session.add(RolesUser(user_id=user_id, role_id=role.id, active=True))
    database.session.add(UserCompanyAccess(user_id=user_id, company_code=company))
    return user_id


def _login(app, user_id: str):
    """Devuelve un cliente autenticado sin repetir el flujo de contraseña."""
    with app.app_context():
        user = database.session.get(User, user_id)
        auth_version = user.auth_version
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    return client


@pytest.fixture
def escenario_remisiones(app, entorno_contable, reference_users):
    """Usuarios con permisos disjuntos y una lista de precios para cacao."""
    with app.app_context():
        inventory_only = _crear_usuario(
            "inventario", "inventory-unico", {"access": True, "view": True, "create": True}, "cacao"
        )
        sales_only = _crear_usuario("ventas", "sales-unico", {"access": True, "view": True, "create": True}, "cacao")
        inventory_view = _crear_usuario("consulta", "inventory-consulta", {"access": True, "view": True}, "cacao")
        alpha_inventory = _crear_usuario(
            "alpha-inv", "inventory-alpha", {"access": True, "view": True, "create": True}, "alpha"
        )
        party = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        price_list = PriceList(
            name=f"Ventas {uuid4().hex[:6]}",
            company="cacao",
            currency="NIO",
            is_selling=True,
            is_default=True,
            is_active=True,
        )
        database.session.add(price_list)
        database.session.flush()
        database.session.add(ItemPrice(item_code="ART01", price_list_id=price_list.id, uom="UND", price=Decimal("10")))
        membership = database.session.execute(
            database.select(CompanyParty).filter_by(company="cacao", party_id=party.id)
        ).scalar_one()
        membership.default_price_list_id = price_list.id
        order = SalesOrder(
            company="cacao",
            document_no=f"SO-{uuid4().hex[:8]}",
            customer_id=party.id,
            customer_name=party.name,
            posting_date=date(2026, 5, 10),
            docstatus=1,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(order)
        database.session.commit()
        return {
            "inventory_only": inventory_only,
            "sales_only": sales_only,
            "inventory_view": inventory_view,
            "alpha_inventory": alpha_inventory,
            "order": order.id,
            "customer": party.id,
        }


def _form_remision(remarks: str, customer_id: str) -> dict[str, str]:
    """Formulario mínimo de una remisión manual con precio de catálogo."""
    return {
        "company": "cacao",
        "posting_date": "2026-05-16",
        "customer_id": customer_id,
        "transaction_currency": "NIO",
        "from_warehouse": "BOD01",
        "remarks": remarks,
        "item_code_0": "ART01",
        "item_name_0": "Articulo Comercial",
        "qty_0": "2",
        "uom_0": "UND",
        "rate_0": "10",
        "amount_0": "20",
    }


def test_inventario_exclusivo_ve_cta_y_formulario(app, escenario_remisiones):
    """El CTA y el GET se habilitan solo con inventory.crear."""
    client = _login(app, escenario_remisiones["inventory_only"])

    assert client.get(RUTA_LISTA).status_code == 200
    listado = client.get(RUTA_LISTA).get_data(as_text=True)
    assert "/delivery-note/new" in listado
    assert client.get(RUTA_ALTA).status_code == 200


def test_inventario_exclusivo_crea_remision_con_trazabilidad(app, escenario_remisiones):
    """El POST de Inventario persiste la remisión y su evento de creación."""
    client = _login(app, escenario_remisiones["inventory_only"])
    remarks = f"Remision inventario {uuid4().hex[:8]}"

    response = client.post(RUTA_ALTA, data=_form_remision(remarks, escenario_remisiones["customer"]))

    assert response.status_code == 302
    with app.app_context():
        note = database.session.execute(database.select(DeliveryNote).filter_by(remarks=remarks)).scalar_one()
        assert note.company == "cacao" and note.docstatus == 0
        assert note.total == Decimal("20.0000")
        trace = database.session.execute(
            database.select(AuditTrail).filter_by(document_type="delivery_note", document_id=note.id, action="created")
        ).scalar_one_or_none()
        assert trace is not None


@pytest.mark.parametrize("role_key", ["sales_only", "inventory_view"])
def test_usuario_sin_inventory_crear_no_accede_al_alta(app, escenario_remisiones, role_key):
    """Ventas sin Inventario, o Inventario sin crear, reciben 403."""
    client = _login(app, escenario_remisiones[role_key])

    assert client.get(RUTA_ALTA).status_code == 403
    assert (
        client.post(
            RUTA_ALTA, data=_form_remision(f"sin permiso {uuid4().hex[:6]}", escenario_remisiones["customer"])
        ).status_code
        == 403
    )


def test_inventario_de_otra_compania_no_crea_en_cacao(app, escenario_remisiones):
    """inventory.crear en Alpha no autoriza crear una remisión de cacao."""
    client = _login(app, escenario_remisiones["alpha_inventory"])
    remarks = f"Remision ajena {uuid4().hex[:8]}"

    response = client.post(RUTA_ALTA, data=_form_remision(remarks, escenario_remisiones["customer"]))

    assert response.status_code == 403
    with app.app_context():
        assert database.session.execute(database.select(DeliveryNote).filter_by(remarks=remarks)).scalar_one_or_none() is None


def test_origen_de_orden_no_expone_datos_comerciales_a_inventario(app, escenario_remisiones):
    """El contexto desde una orden oculta precios y datos comerciales al perfil de Inventario."""
    client = _login(app, escenario_remisiones["inventory_only"])

    response = client.get(f"{RUTA_ALTA}?from_order={escenario_remisiones['order']}")

    assert response.status_code == 200
    pagina = response.get_data(as_text=True)
    inicio = pagina.index("transactionForm(") + len("transactionForm(")
    config = json.loads(pagina[inicio : pagina.index(")'", inicio)])
    assert config["showPricing"] is False
    assert "party" not in config["initialHeader"]
    assert "customer_id" not in config["initialHeader"]
