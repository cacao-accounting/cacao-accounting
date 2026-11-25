# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1606: una orden parcial no cierra la solicitud de compra."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from threading import Event, Thread
from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting import document_flow
from cacao_accounting.document_flow import lock_document_flow_document
from cacao_accounting.approval_engine import ApprovalEngine
from cacao_accounting.compras import routes as compras_routes
from cacao_accounting.compras.services import purchase_order_has_closed_source_request
from cacao_accounting.compras.purchase_request_comparison_service import (
    purchase_request_comparison_covered_item_ids,
    purchase_request_is_ready_to_close,
    purchase_request_line_closure_reasons,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    DocumentRelation,
    Entity,
    Item,
    PurchaseOrder,
    PurchaseOrderItem,
    Modules,
    PurchaseRequest,
    PurchaseRequestComparison,
    PurchaseRequestComparisonLine,
    PurchaseRequestItem,
    SupplierQuotation,
    UOM,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture
def request_order_scene():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    sufijo = uuid4().hex[:6]
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id=f"J-{sufijo}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="UND", name="Unidad"),
                Modules(module="purchases", default=True, enabled=True),
                User(id="admin", user="admin", name="Admin", password=b"unused", classification="admin", active=True),
            ]
        )
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id="admin", company_code="cacao"))
        database.session.add(
            Item(
                code="ART01",
                name="Artículo de prueba",
                item_type="goods",
                is_stock_item=False,
                is_purchase_item=True,
                default_uom="UND",
            )
        )
        database.session.flush()
        solicitud = PurchaseRequest(company="cacao", posting_date=date(2026, 5, 15), docstatus=1, status="open")
        database.session.add(solicitud)
        database.session.flush()
        solicitud_linea = PurchaseRequestItem(
            purchase_request_id=solicitud.id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal("10"),
            uom="UND",
            qty_in_base_uom=Decimal("10"),
            rate=Decimal("10"),
            amount=Decimal("100"),
        )
        database.session.add(solicitud_linea)
        database.session.commit()
        ids = {"request": solicitud.id, "request_item": solicitud_linea.id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _agregar_orden(application, ids, cantidad: str, *, docstatus: int = 1) -> str:
    with application.app_context():
        orden = PurchaseOrder(company="cacao", posting_date=date(2026, 5, 15), docstatus=docstatus, status="open")
        database.session.add(orden)
        database.session.flush()
        linea = PurchaseOrderItem(
            purchase_order_id=orden.id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal(cantidad),
            uom="UND",
            qty_in_base_uom=Decimal(cantidad),
            rate=Decimal("10"),
            amount=Decimal(cantidad) * Decimal("10"),
        )
        database.session.add(linea)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_request",
                source_id=ids["request"],
                source_item_id=ids["request_item"],
                target_type="purchase_order",
                target_id=orden.id,
                target_item_id=linea.id,
                company="cacao",
                qty=Decimal(cantidad),
                qty_in_base_uom=Decimal(cantidad),
                uom="UND",
                rate=Decimal("10"),
                amount=Decimal(cantidad) * Decimal("10"),
                relation_type="order",
                status="active",
            )
        )
        database.session.commit()
        return str(orden.id)


def _cliente_admin(application):
    """Cliente autenticado como el administrador del escenario."""
    with application.app_context():
        version = database.session.get(User, "admin").auth_version
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_auth_version"] = version
        session["_fresh"] = True
    return client


def _agregar_comparativo_finalizado(application, ids) -> None:
    """Finaliza un comparativo sin generar la orden de compra de la línea."""
    suffix = uuid4().hex[:6]
    with application.app_context():
        quotation = SupplierQuotation(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SC-{suffix}",
            supplier_name=f"Proveedor {suffix}",
            transaction_currency="NIO",
        )
        comparison = PurchaseRequestComparison(
            company="cacao",
            purchase_request_id=ids["request"],
            document_no=f"CMP-{suffix}",
            posting_date=date(2026, 5, 15),
            status="finalized",
        )
        database.session.add_all([quotation, comparison])
        database.session.flush()
        database.session.add(
            PurchaseRequestComparisonLine(
                comparison_id=comparison.id,
                purchase_request_item_id=ids["request_item"],
                selected_supplier_quotation_id=quotation.id,
            )
        )
        database.session.commit()


def test_comparativo_finalizado_sin_orden_no_cierra_la_solicitud(request_order_scene):
    """Finalizar el comparativo no sustituye la orden que cubre la cantidad."""
    application, ids = request_order_scene
    _agregar_comparativo_finalizado(application, ids)

    with application.app_context():
        solicitud = database.session.get(PurchaseRequest, ids["request"])
        assert purchase_request_is_ready_to_close(solicitud) is False
        assert purchase_request_line_closure_reasons(solicitud) == {}


def test_orden_en_borrador_no_cubre_la_solicitud(request_order_scene):
    """Una OC en borrador no consume la cantidad pendiente de la solicitud."""
    application, ids = request_order_scene
    _agregar_comparativo_finalizado(application, ids)
    _agregar_orden(application, ids, "10", docstatus=0)

    with application.app_context():
        solicitud = database.session.get(PurchaseRequest, ids["request"])
        assert purchase_request_comparison_covered_item_ids(solicitud) == set()
        assert purchase_request_is_ready_to_close(solicitud) is False


def test_comparativo_finalizado_cierra_cuando_la_orden_cubre_la_linea(request_order_scene):
    """El comparativo acredita cobertura solo después de cubrir la cantidad."""
    application, ids = request_order_scene
    _agregar_comparativo_finalizado(application, ids)
    _agregar_orden(application, ids, "10")

    with application.app_context():
        solicitud = database.session.get(PurchaseRequest, ids["request"])
        assert purchase_request_comparison_covered_item_ids(solicitud) == {ids["request_item"]}
        assert purchase_request_is_ready_to_close(solicitud) is True
        assert ids["request_item"] in purchase_request_line_closure_reasons(solicitud)


def test_orden_parcial_no_cierra_la_solicitud(request_order_scene):
    """Mientras haya cantidad pendiente, la solicitud no está lista para cerrar."""
    application, ids = request_order_scene
    _agregar_orden(application, ids, "4")

    with application.app_context():
        solicitud = database.session.get(PurchaseRequest, ids["request"])
        assert purchase_request_is_ready_to_close(solicitud) is False


@pytest.mark.parametrize(("cantidad", "estado_esperado"), [("4", "open"), ("10", "closed")])
def test_ruta_cierre_solicitud_revalida_pendiente(request_order_scene, cantidad, estado_esperado):
    """El POST de cierre solo marca closed cuando la cantidad queda cubierta."""
    application, ids = request_order_scene
    _agregar_orden(application, ids, cantidad)

    respuesta = _cliente_admin(application).post(f"/buying/purchase-request/{ids['request']}/close")

    assert respuesta.status_code == 302
    with application.app_context():
        assert database.session.get(PurchaseRequest, ids["request"]).status == estado_esperado


def test_cierre_toma_flow_antes_de_releer_la_fila(request_order_scene, monkeypatch):
    """El flujo de la SC se bloquea antes de la recarga FOR UPDATE."""
    application, ids = request_order_scene
    _agregar_orden(application, ids, "10")
    eventos: list[str] = []
    original_lock = compras_routes.lock_document_flow_document
    original_execute = database.session.execute

    def tracking_lock(document_type: str, document_id: str) -> None:
        eventos.append("lock")
        original_lock(document_type, document_id)

    def tracking_execute(statement, *args, **kwargs):
        if getattr(statement, "_for_update_arg", None) is not None and "purchase_request" in str(statement):
            eventos.append("for_update")
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(compras_routes, "lock_document_flow_document", tracking_lock)
    monkeypatch.setattr(database.session, "execute", tracking_execute)
    respuesta = _cliente_admin(application).post(f"/buying/purchase-request/{ids['request']}/close")

    assert respuesta.status_code == 302
    assert "lock" in eventos and "for_update" in eventos
    assert eventos.index("lock") < eventos.index("for_update")


def test_doble_cierre_de_solicitud_no_muta(request_order_scene):
    """El segundo POST de cierre responde 400 y conserva el estado."""
    application, ids = request_order_scene
    _agregar_orden(application, ids, "10")
    client = _cliente_admin(application)
    assert client.post(f"/buying/purchase-request/{ids['request']}/close").status_code == 302
    segundo = client.post(f"/buying/purchase-request/{ids['request']}/close")

    assert segundo.status_code == 400
    with application.app_context():
        assert database.session.get(PurchaseRequest, ids["request"]).status == "closed"


def test_cierre_revalida_estado_cambiado_tras_lock(request_order_scene, monkeypatch):
    """Si la SC se cierra entre la lectura y el lock, el POST responde 400."""
    application, ids = request_order_scene
    _agregar_orden(application, ids, "10")
    original_lock = compras_routes.lock_document_flow_document

    def close_after_lock(document_type: str, document_id: str) -> None:
        original_lock(document_type, document_id)
        if document_type == "purchase_request":
            request = database.session.get(PurchaseRequest, document_id)
            request.status = "closed"
            database.session.commit()

    monkeypatch.setattr(compras_routes, "lock_document_flow_document", close_after_lock)
    respuesta = _cliente_admin(application).post(f"/buying/purchase-request/{ids['request']}/close")

    assert respuesta.status_code == 400
    with application.app_context():
        assert database.session.get(PurchaseRequest, ids["request"]).status == "closed"


def test_ruta_cierre_solicitud_rechaza_comparativo_sin_orden(request_order_scene):
    """Un comparativo finalizado sin orden no permite cerrar por POST."""
    application, ids = request_order_scene
    _agregar_comparativo_finalizado(application, ids)

    respuesta = _cliente_admin(application).post(f"/buying/purchase-request/{ids['request']}/close")

    assert respuesta.status_code == 302
    with application.app_context():
        assert database.session.get(PurchaseRequest, ids["request"]).status == "open"


def test_ruta_cancelar_rechaza_oc_de_solicitud_cerrada(request_order_scene):
    """El POST de cancelación no revierte una OC que cubre una SC cerrada."""
    application, ids = request_order_scene
    order_id = _agregar_orden(application, ids, "10")
    with application.app_context():
        solicitud = database.session.get(PurchaseRequest, ids["request"])
        solicitud.status = "closed"
        database.session.commit()

    respuesta = _cliente_admin(application).post(f"/buying/purchase-order/{order_id}/cancel", data={"reason": "Prueba"})

    assert respuesta.status_code == 302
    with application.app_context():
        assert database.session.get(PurchaseOrder, order_id).docstatus == 1
        assert (
            database.session.execute(
                database.select(DocumentRelation.id).filter_by(
                    target_type="purchase_order", target_id=order_id, status="active"
                )
            ).scalar_one_or_none()
            is not None
        )


def _agregar_segunda_sc_cerrada(application, order_id: str) -> str:
    """Vincula una segunda SC cerrada a la misma orden y devuelve su id."""
    with application.app_context():
        otra = PurchaseRequest(
            id="00000000000000000000000001",
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            status="closed",
        )
        database.session.add(otra)
        database.session.flush()
        linea = PurchaseRequestItem(
            purchase_request_id=otra.id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal("1"),
            uom="UND",
            qty_in_base_uom=Decimal("1"),
            rate=Decimal("10"),
            amount=Decimal("10"),
        )
        database.session.add(linea)
        database.session.flush()
        order_line = PurchaseOrderItem(
            purchase_order_id=order_id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal("1"),
            uom="UND",
            qty_in_base_uom=Decimal("1"),
            rate=Decimal("10"),
            amount=Decimal("10"),
        )
        database.session.add(order_line)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_request",
                source_id=otra.id,
                source_item_id=linea.id,
                target_type="purchase_order",
                target_id=order_id,
                target_item_id=order_line.id,
                company="cacao",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                rate=Decimal("10"),
                amount=Decimal("10"),
                relation_type="order",
                status="active",
            )
        )
        database.session.commit()
        return str(otra.id)


def test_orden_con_dos_solicitudes_bloquea_si_una_esta_cerrada(request_order_scene):
    """El guard considera todas las SC origen, no solo la primera relación."""
    application, ids = request_order_scene
    order_id = _agregar_orden(application, ids, "10")
    _agregar_segunda_sc_cerrada(application, order_id)

    with application.app_context():
        assert purchase_order_has_closed_source_request(order_id) is True
    respuesta = _cliente_admin(application).post(f"/buying/purchase-order/{order_id}/cancel", data={"reason": "Prueba"})
    assert respuesta.status_code == 302
    with application.app_context():
        assert database.session.get(PurchaseOrder, order_id).docstatus == 1


def test_submit_orden_con_dos_solicitudes_bloquea_si_una_esta_cerrada(request_order_scene):
    """El submit considera todas las SC origen, no solo la primera relación."""
    application, ids = request_order_scene
    order_id = _agregar_orden(application, ids, "10", docstatus=0)
    _agregar_segunda_sc_cerrada(application, order_id)

    respuesta = _cliente_admin(application).post(f"/buying/purchase-order/{order_id}/submit")

    assert respuesta.status_code == 302
    with application.app_context():
        assert database.session.get(PurchaseOrder, order_id).docstatus == 0


def test_cancelar_oc_reabre_pendiente_tras_comparativo_finalizado(request_order_scene):
    """Cancelar la OC reabre la SC aunque el comparativo siga finalizado."""
    application, ids = request_order_scene
    order_id = _agregar_orden(application, ids, "10")
    _agregar_comparativo_finalizado(application, ids)

    respuesta = _cliente_admin(application).post(f"/buying/purchase-order/{order_id}/cancel", data={"reason": "Prueba"})
    assert respuesta.status_code == 302

    with application.app_context():
        solicitud = database.session.get(PurchaseRequest, ids["request"])
        assert database.session.get(PurchaseOrder, order_id).docstatus == 2
        assert purchase_request_is_ready_to_close(solicitud) is False
        assert purchase_request_line_closure_reasons(solicitud) == {}


@pytest.mark.parametrize(("accion", "docstatus"), [("submit", 0), ("cancel", 1)])
def test_guard_toma_flows_antes_de_releer_sc(request_order_scene, monkeypatch, accion, docstatus):
    """Submit y cancelación bloquean PO y SC antes de leer el estado."""
    application, ids = request_order_scene
    order_id = _agregar_orden(application, ids, "10", docstatus=docstatus)
    segunda_id = _agregar_segunda_sc_cerrada(application, order_id)
    with application.app_context():
        solicitud = database.session.get(PurchaseRequest, ids["request"])
        solicitud.status = "closed"
        database.session.commit()
    eventos: list[str] = []
    original_lock = compras_routes.lock_document_flow_document
    original_execute = database.session.execute

    def tracking_lock(document_type: str, document_id: str) -> None:
        eventos.append(f"lock:{document_type}:{document_id}")
        original_lock(document_type, document_id)

    def tracking_execute(statement, *args, **kwargs):
        if getattr(statement, "_for_update_arg", None) is not None and "purchase_request" in str(statement):
            eventos.append("for_update")
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(compras_routes, "lock_document_flow_document", tracking_lock)
    monkeypatch.setattr(database.session, "execute", tracking_execute)
    respuesta = _cliente_admin(application).post(
        f"/buying/purchase-order/{order_id}/{accion}",
        data={"reason": "Prueba"} if accion == "cancel" else {},
    )

    assert respuesta.status_code == 302
    assert eventos[0].startswith("lock:purchase_order:")
    esperadas = [f"lock:purchase_request:{request_id}" for request_id in sorted([ids["request"], segunda_id])]
    assert eventos[1:3] == esperadas
    assert eventos[3] == "for_update"


@pytest.mark.parametrize(
    ("accion", "docstatus_inicial", "docstatus_rival"),
    [("submit", 0, 1), ("cancel", 1, 2)],
)
def test_guard_revalida_docstatus_tras_lock(request_order_scene, monkeypatch, accion, docstatus_inicial, docstatus_rival):
    """Un cambio de docstatus entre lectura y lock aborta con 400."""
    application, ids = request_order_scene
    order_id = _agregar_orden(application, ids, "10", docstatus=docstatus_inicial)
    original_lock = compras_routes.lock_document_flow_document
    original_execute = database.session.execute
    eventos: list[str] = []

    def change_after_lock(document_type: str, document_id: str) -> None:
        original_lock(document_type, document_id)
        eventos.append(f"lock:{document_type}")
        if document_type == "purchase_order":
            order = database.session.get(PurchaseOrder, document_id)
            order.docstatus = docstatus_rival
            database.session.commit()

    def tracking_execute(statement, *args, **kwargs):
        if getattr(statement, "_for_update_arg", None) is not None and "purchase_order" in str(statement):
            eventos.append("for_update_purchase_order")
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(compras_routes, "lock_document_flow_document", change_after_lock)
    monkeypatch.setattr(database.session, "execute", tracking_execute)
    respuesta = _cliente_admin(application).post(
        f"/buying/purchase-order/{order_id}/{accion}",
        data={"reason": "Prueba"} if accion == "cancel" else {},
    )

    assert respuesta.status_code == 400
    assert "lock:purchase_order" in eventos
    assert "for_update_purchase_order" in eventos
    assert eventos.index("lock:purchase_order") < eventos.index("for_update_purchase_order")
    with application.app_context():
        assert database.session.get(PurchaseOrder, order_id).docstatus == docstatus_rival


def test_ruta_aprobar_rechaza_oc_borrador_de_solicitud_cerrada(request_order_scene):
    """El POST de aprobación no activa una OC borrador de una SC cerrada."""
    application, ids = request_order_scene
    order_id = _agregar_orden(application, ids, "10", docstatus=0)
    with application.app_context():
        solicitud = database.session.get(PurchaseRequest, ids["request"])
        solicitud.status = "closed"
        database.session.commit()

    respuesta = _cliente_admin(application).post(f"/buying/purchase-order/{order_id}/submit")

    assert respuesta.status_code == 302
    with application.app_context():
        assert database.session.get(PurchaseOrder, order_id).docstatus == 0


def test_motor_aprobaciones_revalida_sc_cerrada(request_order_scene, monkeypatch):
    """El submit y la cancelación del motor rechazan una SC cerrada."""
    application, ids = request_order_scene
    order_id = _agregar_orden(application, ids, "10", docstatus=0)
    segunda_id = _agregar_segunda_sc_cerrada(application, order_id)
    with application.app_context():
        solicitud = database.session.get(PurchaseRequest, ids["request"])
        solicitud.status = "closed"
        database.session.commit()
        order = database.session.get(PurchaseOrder, order_id)
        user = database.session.get(User, "admin")
        assert order is not None and user is not None
        monkeypatch.setattr(ApprovalEngine, "_validate_final_submission", classmethod(lambda cls, doctype, document: None))
        eventos: list[tuple[str, str]] = []
        original_lock = document_flow.lock_document_flow_document
        original_execute = database.session.execute

        def tracking_lock(document_type: str, document_id: str) -> None:
            eventos.append((document_type, document_id))
            original_lock(document_type, document_id)

        def tracking_execute(statement, *args, **kwargs):
            if getattr(statement, "_for_update_arg", None) is not None and "purchase_request" in str(statement):
                eventos.append(("for_update", ""))
            return original_execute(statement, *args, **kwargs)

        monkeypatch.setattr(document_flow, "lock_document_flow_document", tracking_lock)
        monkeypatch.setattr(database.session, "execute", tracking_execute)
        with pytest.raises(ValueError, match="solicitud de compra cerrada"):
            ApprovalEngine._execute_submit("purchase_order", order, user)
        assert [tipo for tipo, _ in eventos] == [
            "purchase_order",
            "purchase_request",
            "purchase_request",
            "for_update",
        ]
        solicitudes = [document_id for document_type, document_id in eventos if document_type == "purchase_request"]
        assert solicitudes == sorted([ids["request"], segunda_id])
        eventos.clear()
        with pytest.raises(ValueError, match="solicitud de compra cerrada"):
            ApprovalEngine._validate_final_cancellation("purchase_order", order)
        assert [tipo for tipo, _ in eventos] == [
            "purchase_order",
            "purchase_request",
            "purchase_request",
            "for_update",
        ]
        solicitudes = [document_id for document_type, document_id in eventos if document_type == "purchase_request"]
        assert solicitudes == sorted([ids["request"], segunda_id])


def test_guard_relee_sc_cerrada_tras_lock(tmp_path):
    """Dos sesiones: el cierre confirmado por otra sesión se observa tras el lock."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'purchase-request-lock.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    suffix = uuid4().hex[:6]
    with app.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.add(UOM(code="UND", name="Unidad"))
        database.session.add(
            Entity(
                code=f"L{suffix}",
                name="Lock",
                company_name="Lock SA",
                tax_id=f"L-{suffix}",
                currency="NIO",
                enabled=True,
            )
        )
        database.session.flush()
        request = PurchaseRequest(company=f"L{suffix}", posting_date=date(2026, 5, 15), docstatus=1, status="open")
        database.session.add(request)
        database.session.flush()
        order = PurchaseOrder(company=f"L{suffix}", posting_date=date(2026, 5, 15), docstatus=0)
        database.session.add(order)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_request",
                source_id=request.id,
                target_type="purchase_order",
                target_id=order.id,
                company=f"L{suffix}",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                rate=Decimal("1"),
                amount=Decimal("1"),
                relation_type="order",
                status="active",
            )
        )
        database.session.commit()
        request_id, order_id = request.id, order.id

    order_read = Event()
    request_closed = Event()
    errors: list[BaseException] = []
    result: list[bool] = []

    def close_request() -> None:
        try:
            assert order_read.wait(timeout=20)
            with app.app_context():
                try:
                    request = database.session.get(PurchaseRequest, request_id)
                    request.status = "closed"
                    database.session.commit()
                    request_closed.set()
                finally:
                    database.session.remove()
        except BaseException as exc:  # pragma: no cover - falla del escenario
            errors.append(exc)

    def read_after_lock() -> None:
        try:
            with app.app_context():
                try:
                    order = database.session.get(PurchaseOrder, order_id)
                    assert order is not None
                    order_read.set()
                    assert request_closed.wait(timeout=20)
                    lock_document_flow_document("purchase_order", order_id)
                    lock_document_flow_document("purchase_request", request_id)
                    result.append(purchase_order_has_closed_source_request(order_id))
                finally:
                    database.session.remove()
        except BaseException as exc:  # pragma: no cover - falla del escenario
            errors.append(exc)

    try:
        closer = Thread(target=close_request)
        reader = Thread(target=read_after_lock)
        closer.start()
        reader.start()
        closer.join(timeout=30)
        reader.join(timeout=30)
        assert not closer.is_alive() and not reader.is_alive()
        assert errors == []
        assert result == [True]
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_ordenes_que_cubren_la_cantidad_cierran_la_solicitud(request_order_scene):
    """Al cubrir las 10 unidades, la solicitud queda lista para cerrar."""
    application, ids = request_order_scene
    _agregar_orden(application, ids, "4")
    order_id = _agregar_orden(application, ids, "6")

    with application.app_context():
        solicitud = database.session.get(PurchaseRequest, ids["request"])
        assert purchase_request_is_ready_to_close(solicitud) is True
        solicitud.status = "closed"
        database.session.commit()
        assert purchase_order_has_closed_source_request(order_id) is True
