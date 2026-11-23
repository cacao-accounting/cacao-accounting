# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La solicitud de cotización solo acepta terceros proveedores.

Escenario de negocio (issue #2136): el alta y la edición manual guardaban el
nombre de cualquier ``supplier_id`` enviado, sin comprobar ``is_supplier``.
La RFQ interna puede no llevar proveedor, pero un ID informado debe tener el
rol correcto.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from flask_login import login_user

from cacao_accounting.compras.services import (
    _create_purchase_quotation_from_request,
    _handle_purchase_quotation_edit_post,
)
from cacao_accounting.database import Party, PurchaseQuotation, PurchaseQuotationItem, User, database

FECHA = date(2026, 5, 15)


def _formulario(supplier_id: str | None) -> dict[str, str]:
    """Datos mínimos que el formulario transaccional envía al alta y edición."""
    datos = {
        "company": "cacao",
        "currency": "NIO",
        "posting_date": FECHA.isoformat(),
        "item_code_0": "ART01",
        "item_name_0": "Articulo Comercial",
        "qty_0": "1",
        "uom_0": "UND",
    }
    if supplier_id:
        datos["supplier_id"] = supplier_id
    return datos


def _tercero(app, *, is_supplier: bool) -> str:
    """Crea un tercero con el rol indicado y devuelve su identificador."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        party = Party(
            code=f"RFQ-{suffix}",
            name=f"Tercero {suffix}",
            is_supplier=is_supplier,
            is_customer=not is_supplier,
            is_active=True,
        )
        database.session.add(party)
        database.session.commit()
        return str(party.id)


def _invocar_alta(app, supplier_id: str | None):
    """Ejecuta el handler de alta con la identidad del administrador."""
    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        with app.test_request_context("/", method="POST", data=_formulario(supplier_id)):
            login_user(admin)
            return _create_purchase_quotation_from_request()


def test_el_alta_rechaza_un_cliente_como_proveedor(app, entorno_contable):
    """Un Party sin rol proveedor no se persiste."""
    cliente_id = _tercero(app, is_supplier=False)
    with app.app_context():
        antes = database.session.execute(database.select(PurchaseQuotation)).scalars().all()

    assert _invocar_alta(app, cliente_id) is None

    with app.app_context():
        despues = database.session.execute(database.select(PurchaseQuotation)).scalars().all()
        assert len(despues) == len(antes)


def test_el_alta_rechaza_un_proveedor_inexistente(app, entorno_contable):
    """Un ID que no existe tampoco crea la solicitud ni deja mutaciones."""
    with app.app_context():
        antes = database.session.execute(database.select(PurchaseQuotation)).scalars().all()

    assert _invocar_alta(app, "NO-EXISTE") is None

    with app.app_context():
        despues = database.session.execute(database.select(PurchaseQuotation)).scalars().all()
        assert len(despues) == len(antes)


def test_el_alta_acepta_proveedor_y_solicitud_sin_proveedor(app, entorno_contable):
    """El control positivo conserva ambos caminos válidos."""
    proveedor_id = _tercero(app, is_supplier=True)

    assert _invocar_alta(app, proveedor_id) is not None
    assert _invocar_alta(app, None) is not None

    with app.app_context():
        cotizaciones = database.session.execute(database.select(PurchaseQuotation)).scalars().all()
        assert {cotizacion.supplier_id for cotizacion in cotizaciones} == {proveedor_id, None}


def test_la_edicion_no_muta_la_cabecera_con_un_cliente(app, entorno_contable):
    """La edición rechaza el cambio y conserva el proveedor original."""
    proveedor_id = _tercero(app, is_supplier=True)
    cliente_id = _tercero(app, is_supplier=False)
    with app.app_context():
        cotizacion = PurchaseQuotation(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            supplier_id=proveedor_id,
            supplier_name="Proveedor original",
            transaction_currency="NIO",
        )
        database.session.add(cotizacion)
        database.session.commit()
        cotizacion_id = cotizacion.id
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        with app.test_request_context("/", method="POST", data=_formulario(cliente_id)):
            login_user(admin)
            respuesta = _handle_purchase_quotation_edit_post(cotizacion)

        assert respuesta is not None
        registro = database.session.execute(database.select(PurchaseQuotation).filter_by(id=cotizacion_id)).scalar_one()
        assert registro.supplier_id == proveedor_id
        assert registro.supplier_name == "Proveedor original"


def test_edicion_con_cantidad_invalida_no_escapa_como_error(app, entorno_contable):
    """#1947: una línea inválida se traduce en respuesta controlada y sin mutación."""
    proveedor_id = _tercero(app, is_supplier=True)
    with app.app_context():
        cotizacion = PurchaseQuotation(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            supplier_id=proveedor_id,
            supplier_name="Proveedor",
            transaction_currency="NIO",
            total=Decimal("20"),
            grand_total=Decimal("20"),
        )
        database.session.add(cotizacion)
        database.session.commit()
        linea_original = PurchaseQuotationItem(
            purchase_quotation_id=cotizacion.id,
            item_code="ART01",
            item_name="Artículo original",
            qty=Decimal("2"),
            qty_in_base_uom=Decimal("2"),
            uom="UND",
            rate=Decimal("10"),
            amount=Decimal("20"),
        )
        database.session.add(linea_original)
        database.session.commit()
        cotizacion_id = cotizacion.id
        linea_id = linea_original.id
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        datos = _formulario(proveedor_id)
        datos.update({"item_code_0": "ITEM-X", "qty_0": "abc", "rate_0": "1"})
        with app.test_request_context("/", method="POST", data=datos):
            login_user(admin)
            respuesta = _handle_purchase_quotation_edit_post(cotizacion)

    assert respuesta is not None
    with app.app_context():
        persistida = database.session.get(PurchaseQuotation, cotizacion_id)
        assert persistida is not None
        assert persistida.docstatus == 0
        assert persistida.total == Decimal("20.0000")
        linea_persistida = database.session.get(PurchaseQuotationItem, linea_id)
        assert linea_persistida is not None
        assert linea_persistida.item_code == "ART01"
        assert linea_persistida.qty == Decimal("2.000000000")
        assert linea_persistida.amount == Decimal("20.0000")
