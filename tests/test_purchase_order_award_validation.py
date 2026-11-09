# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Una orden manual no puede acreditar una adjudicación ajena.

Escenario de negocio: el cliente envía ``purchase_award_id`` de una adjudicación
finalizada de la misma compañía, pero de otro origen, proveedor o líneas. El
servidor debe rechazar la relación en creación y edición.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.compras import services as compras_services
from cacao_accounting.compras.services import (
    _create_purchase_order_from_request,
    _update_purchase_order_from_request,
    _validate_purchase_order_award,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CompanyParty,
    Entity,
    Item,
    Modules,
    Party,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseQuotation,
    PurchaseQuotationAward,
    PurchaseQuotationAwardItem,
    PurchaseQuotationItem,
    SupplierQuotation,
    SupplierQuotationItem,
    UOM,
    User,
    database,
)

FECHA = date(2026, 10, 20)


@pytest.fixture
def adjudicaciones():
    """Adjudicación de Q1/proveedor A, con una fuente y proveedor alternos."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
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
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="purchases", default=False, enabled=True),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        proveedor_a = Party(code="PROV-A", name="Proveedor A", is_supplier=True)
        proveedor_b = Party(code="PROV-B", name="Proveedor B", is_supplier=True)
        item = Item(code="ART-1", name="Artículo", item_type="goods", is_stock_item=True, default_uom="UND")
        database.session.add_all([proveedor_a, proveedor_b, item, UOM(code="UND", name="Unidad")])
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="cacao", party_id=proveedor_a.id, is_active=True),
                CompanyParty(company="cacao", party_id=proveedor_b.id, is_active=True),
            ]
        )
        database.session.flush()
        q1 = PurchaseQuotation(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="RFQ-1",
            transaction_currency="NIO",
        )
        q2 = PurchaseQuotation(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="RFQ-2",
            transaction_currency="NIO",
        )
        database.session.add_all([q1, q2])
        database.session.flush()
        sq_a = SupplierQuotation(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="SQ-A",
            supplier_id=proveedor_a.id,
            purchase_quotation_id=q1.id,
            transaction_currency="NIO",
        )
        sq_b = SupplierQuotation(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no="SQ-B",
            supplier_id=proveedor_b.id,
            purchase_quotation_id=q2.id,
            transaction_currency="NIO",
        )
        database.session.add_all([sq_a, sq_b])
        database.session.flush()
        pq_item = PurchaseQuotationItem(
            purchase_quotation_id=q1.id,
            item_code="ART-1",
            qty=Decimal("5"),
            uom="UND",
            qty_in_base_uom=Decimal("5"),
        )
        sq_item = SupplierQuotationItem(
            supplier_quotation_id=sq_a.id,
            item_code="ART-1",
            qty=Decimal("5"),
            uom="UND",
            qty_in_base_uom=Decimal("5"),
            rate=Decimal("10"),
        )
        database.session.add_all([pq_item, sq_item])
        database.session.flush()
        award = PurchaseQuotationAward(
            purchase_quotation_id=q1.id,
            company="cacao",
            status="finalized",
        )
        database.session.add(award)
        database.session.flush()
        database.session.add(
            PurchaseQuotationAwardItem(
                award_id=award.id,
                purchase_quotation_item_id=pq_item.id,
                supplier_quotation_id=sq_a.id,
                supplier_quotation_item_id=sq_item.id,
                item_code="ART-1",
                qty=Decimal("5"),
                rate=Decimal("10"),
                amount=Decimal("50"),
            )
        )
        database.session.commit()
        ids = {
            "award": award.id,
            "sq_a": sq_a.id,
            "sq_b": sq_b.id,
            "proveedor_a": proveedor_a.id,
            "proveedor_b": proveedor_b.id,
            "sq_item": sq_item.id,
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _form(ids, **overrides):
    form = {
        "supplier_id": ids["proveedor_a"],
        "item_code_0": "ART-1",
        "qty_0": "1",
        "source_item_id_0": ids["sq_item"],
    }
    form.update(overrides)
    return form


def _validar(application, *args, **kwargs):
    with application.test_request_context("/"):
        return _validate_purchase_order_award(*args, **kwargs)


def test_adjudicacion_valida_corresponde_a_origen_proveedor_y_linea(adjudicaciones):
    """Control positivo: Q1, proveedor A y ART-1 son consistentes."""
    application, ids = adjudicaciones
    with application.app_context():
        award = database.session.get(PurchaseQuotationAward, ids["award"])
        source = database.session.get(SupplierQuotation, ids["sq_a"])
        resultado, valido = _validar(
            application,
            ids["award"],
            "cacao",
            source=source,
            supplier_id=ids["proveedor_a"],
            form=_form(ids),
        )
        assert valido is True
        assert resultado is award


def test_adjudicacion_rechaza_proveedor_ajeno(adjudicaciones):
    """El proveedor seleccionado debe ser el de las líneas adjudicadas."""
    application, ids = adjudicaciones
    with application.app_context():
        _, valido = _validar(
            application,
            ids["award"],
            "cacao",
            supplier_id=ids["proveedor_b"],
            form=_form(ids, supplier_id=ids["proveedor_b"]),
        )
        assert valido is False


def test_adjudicacion_rechaza_origen_ajeno(adjudicaciones):
    """La fuente debe pertenecer a la misma solicitud de cotización."""
    application, ids = adjudicaciones
    with application.app_context():
        source = database.session.get(SupplierQuotation, ids["sq_b"])
        _, valido = _validar(
            application,
            ids["award"],
            "cacao",
            source=source,
            supplier_id=ids["proveedor_a"],
            form=_form(ids),
        )
        assert valido is False


def test_adjudicacion_rechaza_linea_no_adjudicada(adjudicaciones):
    """La línea de la orden debe existir en la adjudicación."""
    application, ids = adjudicaciones
    with application.app_context():
        _, valido = _validar(
            application,
            ids["award"],
            "cacao",
            supplier_id=ids["proveedor_a"],
            form=_form(ids, item_code_0="OTRO"),
        )
        assert valido is False


def test_adjudicacion_rechaza_orden_sin_origen(adjudicaciones):
    """Una orden que acredita una adjudicación debe declarar su origen."""
    application, ids = adjudicaciones
    with application.app_context():
        _, valido = _validar(
            application,
            ids["award"],
            "cacao",
            source=None,
            supplier_id=ids["proveedor_a"],
            form=_form(ids),
        )
        assert valido is False


def test_adjudicacion_rechaza_orden_sin_proveedor(adjudicaciones):
    """Una orden que acredita una adjudicación debe declarar proveedor."""
    application, ids = adjudicaciones
    with application.app_context():
        _, valido = _validar(
            application,
            ids["award"],
            "cacao",
            source=database.session.get(SupplierQuotation, ids["sq_a"]),
            supplier_id=None,
            form=_form(ids, supplier_id=None),
        )
        assert valido is False


def test_adjudicacion_rechaza_cantidades_repetidas_sobre_el_total(adjudicaciones):
    """Dos líneas del mismo ítem no pueden superar el total adjudicado."""
    application, ids = adjudicaciones
    with application.app_context():
        form = _form(ids, qty_0="4")
        form.update({"item_code_1": "ART-1", "qty_1": "4", "source_item_id_1": ids["sq_item"]})
        _, valido = _validar(
            application,
            ids["award"],
            "cacao",
            source=database.session.get(SupplierQuotation, ids["sq_a"]),
            supplier_id=ids["proveedor_a"],
            form=form,
        )
        assert valido is False


def _form_orden(ids, **overrides):
    form = {
        "company": "cacao",
        "supplier_id": ids["proveedor_a"],
        "posting_date": FECHA.isoformat(),
        "transaction_currency": "NIO",
        "purchase_award_id": ids["award"],
        "from_supplier_quotation": ids["sq_a"],
        "item_code_0": "ART-1",
        "qty_0": "1",
        "rate_0": "10",
        "uom_0": "UND",
        "source_type_0": "supplier_quotation",
        "source_id_0": ids["sq_a"],
        "source_item_id_0": ids["sq_item"],
    }
    form.update(overrides)
    return form


def _crear_orden(application, ids, monkeypatch, **overrides):
    form = _form_orden(ids, **overrides)
    monkeypatch.setattr(compras_services, "assign_document_identifier", lambda **kwargs: None)
    from flask_login import login_user

    with application.test_request_context("/buying/purchase-order/new", method="POST", data=form):
        login_user(database.session.get(User, "admin"))
        return _create_purchase_order_from_request(form)


def test_creacion_guarda_orden_con_adjudicacion_valida(adjudicaciones, monkeypatch):
    """El alta real persiste una orden vinculada a su adjudicación."""
    application, ids = adjudicaciones

    _crear_orden(application, ids, monkeypatch)

    with application.app_context():
        ordenes = database.session.execute(database.select(PurchaseOrder)).scalars().all()
        assert len(ordenes) == 1
        assert ordenes[0].purchase_award_id == ids["award"]
        assert ordenes[0].supplier_id == ids["proveedor_a"]


def test_creacion_rechaza_adjudicacion_sin_origen(adjudicaciones, monkeypatch):
    """El POST sin documento origen no crea la orden."""
    application, ids = adjudicaciones
    form = _form_orden(ids)
    form.pop("from_supplier_quotation")
    form.pop("source_type_0")
    form.pop("source_id_0")
    monkeypatch.setattr(compras_services, "assign_document_identifier", lambda **kwargs: None)
    from flask_login import login_user

    with application.test_request_context("/buying/purchase-order/new", method="POST", data=form):
        login_user(database.session.get(User, "admin"))
        _create_purchase_order_from_request(form)

    with application.app_context():
        assert database.session.execute(database.select(PurchaseOrder)).scalars().all() == []


def test_creacion_rechaza_adjudicacion_sin_proveedor(adjudicaciones, monkeypatch):
    """El POST que omite el proveedor no crea la orden."""
    application, ids = adjudicaciones
    form = _form_orden(ids, supplier_id="")
    monkeypatch.setattr(compras_services, "assign_document_identifier", lambda **kwargs: None)
    from flask_login import login_user

    with application.test_request_context("/buying/purchase-order/new", method="POST", data=form):
        login_user(database.session.get(User, "admin"))
        _create_purchase_order_from_request(form)

    with application.app_context():
        assert database.session.execute(database.select(PurchaseOrder)).scalars().all() == []


def test_edicion_rechaza_cambio_de_proveedor_con_adjudicacion(adjudicaciones, monkeypatch):
    """La edición no puede sustituir el proveedor adjudicado."""
    application, ids = adjudicaciones
    _crear_orden(application, ids, monkeypatch)
    with application.app_context():
        orden_id = database.session.execute(database.select(PurchaseOrder)).scalar_one().id

    form = _form_orden(ids, supplier_id=ids["proveedor_b"])
    from flask_login import login_user

    with application.test_request_context(f"/buying/purchase-order/{orden_id}/edit", method="POST", data=form):
        login_user(database.session.get(User, "admin"))
        orden = database.session.get(PurchaseOrder, orden_id)
        _update_purchase_order_from_request(orden)

    with application.app_context():
        orden = database.session.get(PurchaseOrder, orden_id)
        assert orden.supplier_id == ids["proveedor_a"]
        assert (
            database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=orden_id)).scalars().all()
        )


def test_edicion_rechaza_quitar_proveedor_con_adjudicacion(adjudicaciones, monkeypatch):
    """La edición no puede dejar sin proveedor una orden adjudicada."""
    application, ids = adjudicaciones
    _crear_orden(application, ids, monkeypatch)
    with application.app_context():
        orden_id = database.session.execute(database.select(PurchaseOrder)).scalar_one().id

    form = _form_orden(ids, supplier_id="")
    from flask_login import login_user

    with application.test_request_context(f"/buying/purchase-order/{orden_id}/edit", method="POST", data=form):
        login_user(database.session.get(User, "admin"))
        orden = database.session.get(PurchaseOrder, orden_id)
        _update_purchase_order_from_request(orden)

    with application.app_context():
        orden = database.session.get(PurchaseOrder, orden_id)
        assert orden.supplier_id == ids["proveedor_a"]


def test_edicion_conserva_orden_con_linea_adjudicada(adjudicaciones, monkeypatch):
    """Una edición válida conserva la adjudicación y las líneas."""
    application, ids = adjudicaciones
    _crear_orden(application, ids, monkeypatch)
    with application.app_context():
        orden_id = database.session.execute(database.select(PurchaseOrder)).scalar_one().id

    form = _form_orden(ids, remarks="Actualizada")
    from flask_login import login_user

    with application.test_request_context(f"/buying/purchase-order/{orden_id}/edit", method="POST", data=form):
        login_user(database.session.get(User, "admin"))
        orden = database.session.get(PurchaseOrder, orden_id)
        _update_purchase_order_from_request(orden)

    with application.app_context():
        orden = database.session.get(PurchaseOrder, orden_id)
        assert orden.purchase_award_id == ids["award"]
        assert orden.remarks == "Actualizada"
