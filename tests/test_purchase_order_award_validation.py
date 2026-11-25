# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Una orden manual no puede acreditar una adjudicación ajena.

Escenario de negocio: el cliente envía ``purchase_award_id`` de una adjudicación
finalizada de la misma compañía, pero de otro origen, proveedor o líneas. El
servidor debe rechazar la relación en creación y edición.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier, Event, current_thread
from uuid import uuid4

import pytest
from flask import get_flashed_messages
from sqlalchemy import event, text

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
    DocumentRelation,
    Currency,
    Entity,
    Item,
    ItemUOMConversion,
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

pytestmark = pytest.mark.database


@pytest.fixture
def adjudicaciones(tmp_path):
    """Adjudicación de Q1/proveedor A, con una fuente y proveedor alternos."""
    import os

    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        uri = f"sqlite:///{tmp_path / 'purchase_awards.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        sufijo = uuid4().hex[:6].upper()
        company = f"CA-{sufijo}"
        item_code = f"ART-1-{sufijo}"
        item_code_2 = f"ART-2-{sufijo}"
        user_id = f"admin-{sufijo}"
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
            database.session.flush()
        if database.session.execute(database.select(Modules).filter_by(module="purchases")).scalar_one_or_none() is None:
            database.session.add(Modules(module="purchases", default=False, enabled=True))
        database.session.add_all(
            [
                Entity(
                    code=company,
                    name=f"Cacao {sufijo}",
                    company_name=f"Cacao SA {sufijo}",
                    tax_id=f"J-{sufijo}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id=user_id,
                    user=user_id,
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        for codigo, nombre in (("UND", "Unidad"), ("BOX", "Caja")):
            if database.session.execute(database.select(UOM).filter_by(code=codigo)).scalar_one_or_none() is None:
                database.session.add(UOM(code=codigo, name=nombre))
        database.session.flush()
        proveedor_a = Party(code=f"PROV-A-{sufijo}", name="Proveedor A", is_supplier=True)
        proveedor_b = Party(code=f"PROV-B-{sufijo}", name="Proveedor B", is_supplier=True)
        item = Item(code=item_code, name="Artículo", item_type="goods", is_stock_item=True, default_uom="UND")
        database.session.add_all([proveedor_a, proveedor_b, item])
        database.session.flush()
        database.session.add(
            ItemUOMConversion(item_code=item_code, from_uom="BOX", to_uom="UND", conversion_factor=Decimal("2"))
        )
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company=company, party_id=proveedor_a.id, is_active=True),
                CompanyParty(company=company, party_id=proveedor_b.id, is_active=True),
            ]
        )
        database.session.flush()
        q1 = PurchaseQuotation(
            company=company,
            posting_date=FECHA,
            docstatus=1,
            document_no="RFQ-1",
            transaction_currency="NIO",
        )
        q2 = PurchaseQuotation(
            company=company,
            posting_date=FECHA,
            docstatus=1,
            document_no="RFQ-2",
            transaction_currency="NIO",
        )
        database.session.add_all([q1, q2])
        database.session.flush()
        sq_a = SupplierQuotation(
            company=company,
            posting_date=FECHA,
            docstatus=1,
            document_no="SQ-A",
            supplier_id=proveedor_a.id,
            purchase_quotation_id=q1.id,
            transaction_currency="NIO",
        )
        sq_b = SupplierQuotation(
            company=company,
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
            item_code=item_code,
            qty=Decimal("50"),
            uom="UND",
            qty_in_base_uom=Decimal("50"),
        )
        sq_item = SupplierQuotationItem(
            supplier_quotation_id=sq_a.id,
            item_code=item_code,
            qty=Decimal("5"),
            uom="BOX",
            qty_in_base_uom=Decimal("50"),
            rate=Decimal("10"),
        )
        database.session.add_all([pq_item, sq_item])
        database.session.flush()
        sq_b_item = SupplierQuotationItem(
            supplier_quotation_id=sq_b.id,
            item_code=item_code,
            qty=Decimal("5"),
            uom="UND",
            qty_in_base_uom=Decimal("5"),
            rate=Decimal("12"),
        )
        database.session.add(sq_b_item)
        database.session.flush()
        item_2 = Item(code=item_code_2, name="Artículo 2", item_type="goods", is_stock_item=True, default_uom="UND")
        database.session.add(item_2)
        database.session.flush()
        sq_b_q1 = SupplierQuotation(
            company=company,
            posting_date=FECHA,
            docstatus=1,
            document_no="SQ-B-Q1",
            supplier_id=proveedor_b.id,
            purchase_quotation_id=q1.id,
            transaction_currency="NIO",
        )
        database.session.add(sq_b_q1)
        database.session.flush()
        pq_item_2 = PurchaseQuotationItem(
            purchase_quotation_id=q1.id,
            item_code=item_code_2,
            qty=Decimal("5"),
            uom="UND",
            qty_in_base_uom=Decimal("5"),
        )
        sq_b_q1_item = SupplierQuotationItem(
            supplier_quotation_id=sq_b_q1.id,
            item_code=item_code_2,
            qty=Decimal("5"),
            uom="UND",
            qty_in_base_uom=Decimal("5"),
            rate=Decimal("12"),
        )
        database.session.add_all([pq_item_2, sq_b_q1_item])
        database.session.flush()
        award = PurchaseQuotationAward(
            purchase_quotation_id=q1.id,
            company=company,
            status="finalized",
        )
        database.session.add(award)
        database.session.flush()
        database.session.add_all(
            [
                PurchaseQuotationAwardItem(
                    award_id=award.id,
                    purchase_quotation_item_id=pq_item.id,
                    supplier_quotation_id=sq_a.id,
                    supplier_quotation_item_id=sq_item.id,
                    item_code=item_code,
                    qty=Decimal("5"),
                    rate=Decimal("10"),
                    amount=Decimal("50"),
                ),
                PurchaseQuotationAwardItem(
                    award_id=award.id,
                    purchase_quotation_item_id=pq_item_2.id,
                    supplier_quotation_id=sq_b_q1.id,
                    supplier_quotation_item_id=sq_b_q1_item.id,
                    item_code=item_code_2,
                    qty=Decimal("5"),
                    rate=Decimal("12"),
                    amount=Decimal("60"),
                ),
            ]
        )
        database.session.commit()
        ids = {
            "award": award.id,
            "sq_a": sq_a.id,
            "sq_b": sq_b.id,
            "proveedor_a": proveedor_a.id,
            "proveedor_b": proveedor_b.id,
            "sq_item": sq_item.id,
            "sq_b_item": sq_b_item.id,
            "company": company,
            "item_code": item_code,
            "item_code_2": item_code_2,
            "user": user_id,
            "uom_base": "UND",
            "uom_box": "BOX",
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _form(ids, **overrides):
    form = {
        "supplier_id": ids["proveedor_a"],
        "item_code_0": ids["item_code"],
        "qty_0": "1",
        "source_item_id_0": ids["sq_item"],
        "uom_0": "BOX",
        "rate_0": "10",
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
            ids["company"],
            source=source,
            supplier_id=ids["proveedor_a"],
            form=_form(ids),
        )
        assert valido is True
        assert resultado is award


def test_award_multisupplier_valida_orden_por_sus_lineas(adjudicaciones):
    """An order for one awarded supplier remains valid in a multi-supplier award."""
    application, ids = adjudicaciones
    with application.app_context():
        award = database.session.get(PurchaseQuotationAward, ids["award"])
        resultado, valido = _validar(
            application,
            ids["award"],
            ids["company"],
            source=database.session.get(SupplierQuotation, ids["sq_a"]),
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
            ids["company"],
            source=database.session.get(SupplierQuotation, ids["sq_a"]),
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
            ids["company"],
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
            ids["company"],
            source=database.session.get(SupplierQuotation, ids["sq_a"]),
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
            ids["company"],
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
            ids["company"],
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
        form.update({"item_code_1": ids["item_code"], "qty_1": "4", "source_item_id_1": ids["sq_item"]})
        _, valido = _validar(
            application,
            ids["award"],
            ids["company"],
            source=database.session.get(SupplierQuotation, ids["sq_a"]),
            supplier_id=ids["proveedor_a"],
            form=form,
        )
        assert valido is False


def test_creacion_rechaza_tarifa_no_finita_sin_500(adjudicaciones, monkeypatch):
    """#1544: una tarifa Infinity en el alta devuelve validación, no 500."""
    application, ids = adjudicaciones
    form = {
        "company": ids["company"],
        "supplier_id": ids["proveedor_a"],
        "posting_date": FECHA.isoformat(),
        "transaction_currency": "NIO",
        "item_code_0": ids["item_code"],
        "qty_0": "1",
        "rate_0": "Infinity",
        "uom_0": "BOX",
    }
    monkeypatch.setattr(compras_services, "assign_document_identifier", lambda **kwargs: None)
    from flask_login import login_user

    with application.test_request_context("/buying/purchase-order/new", method="POST", data=form):
        login_user(database.session.get(User, ids["user"]))
        resultado = _create_purchase_order_from_request(form)

    assert resultado is None
    with application.app_context():
        ordenes = (
            database.session.execute(database.select(PurchaseOrder).where(PurchaseOrder.company == ids["company"]))
            .scalars()
            .all()
        )
        assert ordenes == []


@pytest.mark.parametrize("qty", ["0", "-1", "Infinity", "NaN"])
def test_adjudicacion_rechaza_cantidad_no_positiva_o_no_finita(adjudicaciones, qty):
    """Partial order quantities must be finite and positive."""
    application, ids = adjudicaciones
    with application.app_context():
        _, valido = _validar(
            application,
            ids["award"],
            ids["company"],
            source=database.session.get(SupplierQuotation, ids["sq_a"]),
            supplier_id=ids["proveedor_a"],
            form=_form(ids, qty_0=qty),
        )
        assert valido is False


@pytest.mark.parametrize("field,value", [("uom_0", "UND"), ("rate_0", "11")])
def test_adjudicacion_rechaza_cambiar_uom_o_precio(adjudicaciones, field, value):
    """A manual order cannot override terms authorized by the award."""
    application, ids = adjudicaciones
    with application.app_context():
        _, valido = _validar(
            application,
            ids["award"],
            ids["company"],
            source=database.session.get(SupplierQuotation, ids["sq_a"]),
            supplier_id=ids["proveedor_a"],
            form=_form(ids, **{field: value}),
        )
        assert valido is False


def test_orden_generada_conserva_uom_y_conversion_de_la_oferta(adjudicaciones, monkeypatch):
    """Award conversion uses the awarded supplier line, not the RFQ unit."""
    application, ids = adjudicaciones
    monkeypatch.setattr(compras_services, "assign_document_identifier", lambda **kwargs: None)
    monkeypatch.setattr(compras_services, "log_create", lambda *args, **kwargs: None)
    with application.app_context():
        award = database.session.get(PurchaseQuotationAward, ids["award"])
        orders = compras_services._create_purchase_orders_from_award(award)
        database.session.flush()

        line = database.session.execute(
            database.select(PurchaseOrderItem).filter_by(purchase_order_id=orders[0].id)
        ).scalar_one()
        relation = database.session.execute(
            database.select(DocumentRelation).filter_by(target_item_id=line.id, status="active")
        ).scalar_one()
        assert line.uom == "BOX"
        assert line.qty_in_base_uom == Decimal("50.000000000")
        assert relation.uom == "BOX"
        assert relation.qty_in_base_uom == Decimal("50.000000000")


def test_creacion_manual_usa_conversion_base_persistida_en_la_oferta(adjudicaciones, monkeypatch):
    """An award-linked manual order keeps the supplier quote's base quantity snapshot."""
    application, ids = adjudicaciones
    monkeypatch.setattr(compras_services, "assign_document_identifier", lambda **kwargs: None)
    with application.app_context():
        conversion = database.session.execute(
            database.select(ItemUOMConversion).filter_by(item_code=ids["item_code"], from_uom="BOX", to_uom="UND")
        ).scalar_one()
        database.session.delete(conversion)
        database.session.flush()
        form = _form_orden(ids, uom_0="BOX")
        monkeypatch.setattr(compras_services, "log_create", lambda *args, **kwargs: None)
        from flask_login import login_user

        with application.test_request_context("/buying/purchase-order/new", method="POST", data=form):
            login_user(database.session.get(User, ids["user"]))
            compras_services._create_purchase_order_from_request(form)

        line = database.session.execute(
            database.select(PurchaseOrderItem).join(PurchaseOrder).where(PurchaseOrder.company == ids["company"])
        ).scalar_one()
        relation = database.session.execute(
            database.select(DocumentRelation).filter_by(target_item_id=line.id, status="active")
        ).scalar_one()
        assert line.uom == "BOX"
        assert line.qty_in_base_uom == Decimal("10.000000000")
        assert relation.uom == "BOX"
        assert relation.qty_in_base_uom == Decimal("10.000000000")


def test_ordenes_parciales_no_superan_saldo_adjudicado(adjudicaciones, monkeypatch):
    """Separate manual orders cannot consume more than one award line permits."""
    application, ids = adjudicaciones
    with application.app_context():
        award_line = database.session.execute(
            database.select(PurchaseQuotationAwardItem).filter_by(item_code=ids["item_code"])
        ).scalar_one()
        rfq_line = database.session.get(PurchaseQuotationItem, award_line.purchase_quotation_item_id)
        rfq_line.qty = Decimal("5")
        rfq_line.qty_in_base_uom = Decimal("5")
        award_line.qty = Decimal("0.5")
        award_line.amount = Decimal("5")
        database.session.commit()

    _crear_orden(application, ids, monkeypatch, qty_0="0.3")
    _crear_orden(application, ids, monkeypatch, qty_0="0.3")

    with application.app_context():
        orders = (
            database.session.execute(database.select(PurchaseOrder).where(PurchaseOrder.company == ids["company"]))
            .scalars()
            .all()
        )
        assert len(orders) == 1
        line = database.session.execute(
            database.select(PurchaseOrderItem).filter_by(purchase_order_id=orders[0].id)
        ).scalar_one()
        assert line.qty == Decimal("0.3")


def test_ordenes_concurrentes_no_superan_saldo_adjudicado(adjudicaciones, monkeypatch):
    """Concurrent partial orders serialize on the canonical awarded line."""
    application, ids = adjudicaciones
    monkeypatch.setattr(compras_services, "assign_document_identifier", lambda **kwargs: None)
    with application.app_context():
        award_line = database.session.execute(
            database.select(PurchaseQuotationAwardItem).filter_by(item_code=ids["item_code"])
        ).scalar_one()
        rfq_line = database.session.get(PurchaseQuotationItem, award_line.purchase_quotation_item_id)
        rfq_line.qty = Decimal("5")
        rfq_line.qty_in_base_uom = Decimal("5")
        award_line.qty = Decimal("0.5")
        award_line.amount = Decimal("5")
        database.session.commit()
        database.session.remove()

    barrier = Barrier(2)

    def create_partial_order() -> bool:
        form = _form_orden(ids, qty_0="0.3")
        with application.app_context():
            with application.test_request_context("/buying/purchase-order/new", method="POST", data=form):
                from flask_login import login_user

                login_user(database.session.get(User, ids["user"]))
                barrier.wait(timeout=10)
                result = _create_purchase_order_from_request(form)
            database.session.remove()
            return result is not None

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(lambda _index: create_partial_order(), range(2)))

    assert sorted(outcomes) == [False, True]
    with application.app_context():
        orders = (
            database.session.execute(database.select(PurchaseOrder).where(PurchaseOrder.company == ids["company"]))
            .scalars()
            .all()
        )
        assert len(orders) == 1


def test_mysql_orden_manual_ve_estado_confirmado_durante_snapshot(adjudicaciones, monkeypatch):
    """En MySQL la orden manual no reutiliza un award agotado mientras esperaba el lock."""
    application, ids = adjudicaciones
    with application.app_context():
        if database.session.get_bind().dialect.name != "mysql":
            pytest.skip("La regresión de snapshot requiere MySQL.")
        isolation = database.session.execute(text("SELECT @@transaction_isolation")).scalar_one()
        if str(isolation).replace("_", "-").upper() != "REPEATABLE-READ":
            pytest.skip("La regresión requiere el aislamiento MySQL REPEATABLE READ.")
        database.session.remove()

    monkeypatch.setattr(compras_services, "assign_document_identifier", lambda **kwargs: None)
    monkeypatch.setattr(compras_services, "log_create", lambda *args, **kwargs: None)
    hilo_perdedor = []
    lock_alcanzado = Event()
    ganador_confirmo = Event()

    def detener_al_perdedor_antes_del_lock(_conn, _cursor, statement, _params, _context, _executemany) -> None:
        if current_thread() is not hilo_perdedor[0] or "document_flow_lock" not in statement.lower():
            return
        lock_alcanzado.set()
        if not ganador_confirmo.wait(timeout=30):
            raise RuntimeError("La transacción ganadora no confirmó a tiempo.")

    def orden_manual_tras_snapshot():
        hilo_perdedor.append(current_thread())
        form = _form_orden(ids, qty_0="0.3")
        with application.app_context():
            with application.test_request_context("/buying/purchase-order/new", method="POST", data=form):
                from flask_login import login_user

                login_user(database.session.get(User, ids["user"]))
                resultado = _create_purchase_order_from_request(form)
                mensajes = list(get_flashed_messages())
            database.session.remove()
        return resultado, mensajes

    event.listen(database.engine, "before_cursor_execute", detener_al_perdedor_antes_del_lock)
    try:
        with ThreadPoolExecutor(max_workers=1) as workers:
            futuro = workers.submit(orden_manual_tras_snapshot)
            assert lock_alcanzado.wait(timeout=15)
            with application.app_context():
                award = database.session.get(PurchaseQuotationAward, ids["award"])
                compras_services._create_purchase_orders_from_award(award)
                database.session.commit()
                database.session.remove()
            ganador_confirmo.set()
            resultado, mensajes = futuro.result(timeout=30)
    finally:
        event.remove(database.engine, "before_cursor_execute", detener_al_perdedor_antes_del_lock)

    assert resultado is None
    assert "La adjudicación seleccionada no es válida." in mensajes
    with application.app_context():
        award = database.session.get(PurchaseQuotationAward, ids["award"])
        assert award.status == "used"


def _form_orden(ids, **overrides):
    form = {
        "company": ids["company"],
        "supplier_id": ids["proveedor_a"],
        "posting_date": FECHA.isoformat(),
        "transaction_currency": "NIO",
        "purchase_award_id": ids["award"],
        "from_supplier_quotation": ids["sq_a"],
        "item_code_0": ids["item_code"],
        "qty_0": "1",
        "rate_0": "10",
        "uom_0": "BOX",
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
        login_user(database.session.get(User, ids["user"]))
        return _create_purchase_order_from_request(form)


def test_creacion_guarda_orden_con_adjudicacion_valida(adjudicaciones, monkeypatch):
    """El alta real persiste una orden vinculada a su adjudicación."""
    application, ids = adjudicaciones

    _crear_orden(application, ids, monkeypatch)

    with application.app_context():
        ordenes = (
            database.session.execute(database.select(PurchaseOrder).where(PurchaseOrder.company == ids["company"]))
            .scalars()
            .all()
        )
        assert len(ordenes) == 1
        assert ordenes[0].purchase_award_id == ids["award"]
        assert ordenes[0].supplier_id == ids["proveedor_a"]


@pytest.mark.parametrize("field,value", [("uom_0", "UND"), ("rate_0", "11")])
def test_creacion_rechaza_cambios_de_uom_o_precio_adjudicados(adjudicaciones, monkeypatch, field, value):
    """The purchase-order endpoint rejects commercial terms outside the award."""
    application, ids = adjudicaciones
    _crear_orden(application, ids, monkeypatch, **{field: value})

    with application.app_context():
        assert (
            database.session.execute(database.select(PurchaseOrder).where(PurchaseOrder.company == ids["company"]))
            .scalars()
            .all()
            == []
        )


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
        login_user(database.session.get(User, ids["user"]))
        _create_purchase_order_from_request(form)

    with application.app_context():
        assert (
            database.session.execute(database.select(PurchaseOrder).where(PurchaseOrder.company == ids["company"]))
            .scalars()
            .all()
            == []
        )


def test_creacion_rechaza_adjudicacion_sin_proveedor(adjudicaciones, monkeypatch):
    """El POST que omite el proveedor no crea la orden."""
    application, ids = adjudicaciones
    form = _form_orden(ids, supplier_id="")
    monkeypatch.setattr(compras_services, "assign_document_identifier", lambda **kwargs: None)
    from flask_login import login_user

    with application.test_request_context("/buying/purchase-order/new", method="POST", data=form):
        login_user(database.session.get(User, ids["user"]))
        _create_purchase_order_from_request(form)

    with application.app_context():
        assert (
            database.session.execute(database.select(PurchaseOrder).where(PurchaseOrder.company == ids["company"]))
            .scalars()
            .all()
            == []
        )


def test_edicion_rechaza_cambio_de_proveedor_con_adjudicacion(adjudicaciones, monkeypatch):
    """La edición no puede sustituir el proveedor adjudicado."""
    application, ids = adjudicaciones
    _crear_orden(application, ids, monkeypatch)
    with application.app_context():
        orden_id = (
            database.session.execute(database.select(PurchaseOrder).where(PurchaseOrder.company == ids["company"]))
            .scalar_one()
            .id
        )

    form = _form_orden(ids, supplier_id=ids["proveedor_b"])
    from flask_login import login_user

    with application.test_request_context(f"/buying/purchase-order/{orden_id}/edit", method="POST", data=form):
        login_user(database.session.get(User, ids["user"]))
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
        orden_id = (
            database.session.execute(database.select(PurchaseOrder).where(PurchaseOrder.company == ids["company"]))
            .scalar_one()
            .id
        )

    form = _form_orden(ids, supplier_id="")
    from flask_login import login_user

    with application.test_request_context(f"/buying/purchase-order/{orden_id}/edit", method="POST", data=form):
        login_user(database.session.get(User, ids["user"]))
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
        orden_id = (
            database.session.execute(database.select(PurchaseOrder).where(PurchaseOrder.company == ids["company"]))
            .scalar_one()
            .id
        )

    form = _form_orden(ids, remarks="Actualizada")
    from flask_login import login_user

    with application.test_request_context(f"/buying/purchase-order/{orden_id}/edit", method="POST", data=form):
        login_user(database.session.get(User, ids["user"]))
        orden = database.session.get(PurchaseOrder, orden_id)
        _update_purchase_order_from_request(orden)

    with application.app_context():
        orden = database.session.get(PurchaseOrder, orden_id)
        assert orden.purchase_award_id == ids["award"]
        assert orden.remarks == "Actualizada"


def _orden_creada(application, ids) -> str:  # noqa: ANN001 - fixture helper
    """Devuelve el identificador de la única orden persistida."""
    with application.app_context():
        return (
            database.session.execute(database.select(PurchaseOrder).where(PurchaseOrder.company == ids["company"]))
            .scalar_one()
            .id
        )


def _linea_orden(application, orden_id: str) -> PurchaseOrderItem:  # noqa: ANN001 - fixture helper
    """Carga la única línea persistida de la orden."""
    with application.app_context():
        return database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=orden_id)).scalar_one()


def _editar_orden(application, ids, orden_id: str, form: dict) -> None:  # noqa: ANN001 - fixture helper
    """Ejecuta el POST de edición de la orden con el formulario indicado."""
    from flask_login import login_user

    with application.test_request_context(f"/buying/purchase-order/{orden_id}/edit", method="POST", data=form):
        login_user(database.session.get(User, ids["user"]))
        orden = database.session.get(PurchaseOrder, orden_id)
        _update_purchase_order_from_request(orden)


def test_edicion_rechaza_exceder_cantidad_adjudicada(adjudicaciones, monkeypatch):
    """La edición no puede pedir más cantidad de la adjudicada."""
    application, ids = adjudicaciones
    _crear_orden(application, ids, monkeypatch)
    orden_id = _orden_creada(application, ids)

    _editar_orden(application, ids, orden_id, _form_orden(ids, qty_0="6"))

    with application.app_context():
        orden = database.session.get(PurchaseOrder, orden_id)
        linea = _linea_orden(application, orden_id)
        assert orden.purchase_award_id == ids["award"]
        assert orden.supplier_id == ids["proveedor_a"]
        assert linea.item_code == ids["item_code"]
        assert linea.qty == Decimal("1")


def _relaciones_de_orden(application, orden_id: str) -> set[tuple[str | None, str | None]]:  # noqa: ANN001 - helper
    """Devuelve las relaciones activas de origen de la orden."""
    with application.app_context():
        relaciones = database.session.execute(
            database.select(DocumentRelation).filter_by(
                target_type="purchase_order",
                target_id=orden_id,
                status="active",
            )
        ).scalars()
        return {(relacion.source_id, relacion.source_item_id) for relacion in relaciones}


def test_edicion_rechaza_linea_de_fuente_no_adjudicada(adjudicaciones, monkeypatch):
    """Una edición con fuente coherente de otra cotización no rompe la adjudicación."""
    application, ids = adjudicaciones
    _crear_orden(application, ids, monkeypatch)
    orden_id = _orden_creada(application, ids)
    linea_id = _linea_orden(application, orden_id).id
    relaciones = _relaciones_de_orden(application, orden_id)

    _editar_orden(
        application,
        ids,
        orden_id,
        _form_orden(ids, source_id_0=ids["sq_b"], source_item_id_0=ids["sq_b_item"]),
    )

    with application.app_context():
        orden = database.session.get(PurchaseOrder, orden_id)
        linea = _linea_orden(application, orden_id)
        assert orden.purchase_award_id == ids["award"]
        assert orden.supplier_id == ids["proveedor_a"]
        assert linea.id == linea_id
        assert linea.item_code == ids["item_code"]
        assert linea.qty == Decimal("1")
    assert _relaciones_de_orden(application, orden_id) == relaciones


def test_edicion_valida_conserva_articulo_fuente_y_cantidad(adjudicaciones, monkeypatch):
    """Una edición dentro de lo adjudicado persiste artículo, fuente y cantidad."""
    application, ids = adjudicaciones
    _crear_orden(application, ids, monkeypatch)
    orden_id = _orden_creada(application, ids)

    _editar_orden(application, ids, orden_id, _form_orden(ids, qty_0="3", remarks="Cantidad ajustada"))

    with application.app_context():
        orden = database.session.get(PurchaseOrder, orden_id)
        linea = _linea_orden(application, orden_id)
        assert orden.purchase_award_id == ids["award"]
        assert orden.supplier_id == ids["proveedor_a"]
        assert orden.remarks == "Cantidad ajustada"
        assert linea.item_code == ids["item_code"]
        assert linea.qty == Decimal("3")
        assert linea.uom == "BOX"


def test_edicion_con_tarifa_no_finita_preserva_orden(adjudicaciones, monkeypatch):
    """#1544: una tarifa Infinity en edición devuelve validación sin 500.

    El rollback debe restaurar líneas y relaciones ya marcadas y conservar la
    orden original.
    """
    application, ids = adjudicaciones
    _crear_orden(application, ids, monkeypatch)
    orden_id = _orden_creada(application, ids)

    form = _form_orden(ids, rate_0="Infinity")
    with application.test_request_context(f"/buying/purchase-order/{orden_id}/edit", method="POST", data=form):
        from flask_login import login_user

        login_user(database.session.get(User, ids["user"]))
        orden = database.session.get(PurchaseOrder, orden_id)
        response = _update_purchase_order_from_request(orden)

    # Invalid commercial terms are rejected before mutating the order.
    assert response.status_code == 302
    with application.app_context():
        orden = database.session.get(PurchaseOrder, orden_id)
        assert orden.docstatus == 0
        lineas = (
            database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=orden_id)).scalars().all()
        )
        assert len(lineas) == 1
        assert Decimal(str(lineas[0].rate)) == Decimal("10")
        assert orden.purchase_award_id == ids["award"]


@pytest.mark.parametrize("missing", ["source_item_id_0", "source_type_0", "source_id_0"])
def test_edicion_adjudicada_sin_relacion_conserva_lineas(adjudicaciones, monkeypatch, missing):
    """An omitted line source cannot erase the award's documentary evidence."""
    application, ids = adjudicaciones
    _crear_orden(application, ids, monkeypatch)
    orden_id = _orden_creada(application, ids)
    linea_id = _linea_orden(application, orden_id).id
    relaciones = _relaciones_de_orden(application, orden_id)
    form = _form_orden(ids, remarks="No debe guardarse")
    form.pop(missing)

    _editar_orden(application, ids, orden_id, form)

    with application.app_context():
        orden = database.session.get(PurchaseOrder, orden_id)
        assert orden.purchase_award_id == ids["award"]
        assert orden.remarks != "No debe guardarse"
        assert _linea_orden(application, orden_id).id == linea_id
    assert _relaciones_de_orden(application, orden_id) == relaciones


def test_edicion_no_duplica_cantidad_con_alias_de_linea(adjudicaciones, monkeypatch):
    """A quotation row and its RFQ row cannot consume the same award twice."""
    application, ids = adjudicaciones
    _crear_orden(application, ids, monkeypatch)
    orden_id = _orden_creada(application, ids)
    linea_id = _linea_orden(application, orden_id).id
    relaciones = _relaciones_de_orden(application, orden_id)
    with application.app_context():
        rfq_item = (
            database.session.execute(database.select(PurchaseQuotationAwardItem).filter_by(item_code=ids["item_code"]))
            .scalar_one()
            .purchase_quotation_item_id
        )
    form = _form_orden(ids, qty_0="4")
    form.update({"item_code_1": ids["item_code"], "qty_1": "4", "source_item_id_1": rfq_item})

    _editar_orden(application, ids, orden_id, form)

    assert _linea_orden(application, orden_id).id == linea_id
    assert _relaciones_de_orden(application, orden_id) == relaciones
