# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2355: el POST HTTP de la nota física espera la cancelación de la devolución.

La regresión de servicio (`test_purchase_credit_note_physical_return_lock.py`) ejerce
`_physical_return_items_by_code` directamente. Este escenario recorre la ruta completa:
creación de la nota por HTTP, contabilización por HTTP y cancelación concurrente de la
devolución, con el cancelador confirmando la transacción solo cuando el POST ya espera
el lock de fila.
"""

from __future__ import annotations

import html
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from test_purchase_receipt_return_cancel_postgresql import _drop, _isolated_url, _seed

from cacao_accounting import create_app
from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.posting_service import cancel_document, post_purchase_receipt, submit_document
from cacao_accounting.database import (
    Accounts,
    CompanyParty,
    GLEntry,
    Item,
    Modules,
    Party,
    PurchaseCreditNoteAllocation,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseMatchingConfig,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseReceiptReturnAllocation,
    UOM,
    User,
    UserCompanyAccess,
    Warehouse,
    database,
)
from cacao_accounting.internal_control_service import audit_actor

pytestmark = pytest.mark.database

RECHAZO = "La nota física requiere una devolución de recepción aprobada."


def _esperar_bloqueo_de_fila(url, tabla: str, timeout: float = 20.0) -> None:
    """Espera a que la petición de la nota quede esperando un lock de fila.

    PostgreSQL registra la espera de un ``SELECT ... FOR UPDATE`` bloqueado como
    un lock de transacción (``relation`` nulo), por eso se observa
    ``pg_stat_activity`` y no ``pg_locks``: la base es aislada por prueba.
    """
    motor = create_engine(url.render_as_string(hide_password=False))
    limite = time.monotonic() + timeout
    try:
        while time.monotonic() < limite:
            with motor.connect() as conn:
                esperando = conn.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname = current_database() AND wait_event_type = 'Lock'"
                    )
                ).scalar_one()
            if esperando:
                return
            time.sleep(0.05)
    finally:
        motor.dispose()
    raise AssertionError(f"el POST de la nota nunca esperó el lock de fila de {tabla}")


def _habilitar_rutas_http(app) -> None:
    """Activa el módulo de compras y el acceso de admin a la compañía en Cloud."""
    with app.app_context():
        for module_name in ("accounting", "purchases", "inventory", "admin"):
            if database.session.execute(database.select(Modules).filter_by(module=module_name)).scalar_one_or_none() is None:
                database.session.add(Modules(module=module_name, default=module_name == "accounting", enabled=True))
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        if (
            database.session.execute(
                database.select(UserCompanyAccess).filter_by(user_id=admin.id, company_code="cacao")
            ).scalar_one_or_none()
            is None
        ):
            database.session.add(UserCompanyAccess(user_id=admin.id, company_code="cacao"))
        database.session.commit()


def _sembrar_cadena_posteada(app) -> dict[str, object]:
    """Recepción original, factura origen aprobada y devolución físicamente posteada."""
    _habilitar_rutas_http(app)
    with app.app_context():
        config = database.session.execute(
            database.select(PurchaseMatchingConfig).filter_by(company="cacao")
        ).scalar_one_or_none()
        if config is None:
            database.session.add(PurchaseMatchingConfig(company="cacao", require_purchase_order=False, auto_reconcile=True))
        else:
            config.require_purchase_order = False
            config.auto_reconcile = True
        supplier = database.session.execute(database.select(Party).limit(1)).scalar_one()
        if (
            database.session.execute(
                database.select(CompanyParty).filter_by(party_id=supplier.id, company="cacao")
            ).scalar_one_or_none()
            is None
        ):
            database.session.add(
                CompanyParty(
                    company="cacao",
                    party_id=supplier.id,
                    is_active=True,
                    allow_purchase_invoice_without_order=True,
                )
            )
        item = database.session.execute(database.select(Item).limit(1)).scalar_one()
        uom = database.session.execute(database.select(UOM).limit(1)).scalar_one()
        warehouse = database.session.execute(database.select(Warehouse).limit(1)).scalar_one()
        expense = database.session.execute(database.select(Accounts).filter_by(code="5201")).scalar_one()
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        database.session.commit()

        sufijo = uuid4().hex[:8]
        original = PurchaseReceipt(
            company="cacao",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            document_no=f"PR-2355-{sufijo}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("40"),
            base_total=Decimal("40"),
            grand_total=Decimal("40"),
        )
        database.session.add(original)
        database.session.flush()
        database.session.add(
            PurchaseReceiptItem(
                purchase_receipt_id=original.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("4"),
                qty_in_base_uom=Decimal("4"),
                uom=uom.code,
                rate=Decimal("10"),
                amount=Decimal("40"),
                base_amount=Decimal("40"),
                warehouse=warehouse.code,
            )
        )
        database.session.commit()
        with audit_actor(actor.id, actor.name), approved_execution(original, actor.id):
            post_purchase_receipt(original)
        database.session.commit()

        factura = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 10),
            docstatus=0,
            document_no=f"PI-2355-{sufijo}",
            document_type="purchase_invoice",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            purchase_receipt_id=original.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(factura)
        database.session.flush()
        database.session.add(
            PurchaseInvoiceItem(
                purchase_invoice_id=factura.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("4"),
                qty_in_base_uom=Decimal("4"),
                uom=uom.code,
                rate=Decimal("10"),
                amount=Decimal("40"),
                base_amount=Decimal("40"),
                expense_account_id=expense.id,
                warehouse=warehouse.code,
            )
        )
        database.session.commit()
        with audit_actor(actor.id, actor.name), approved_execution(factura, actor.id):
            submit_document(factura)
        database.session.commit()

        devolucion = PurchaseReceipt(
            company="cacao",
            posting_date=date(2026, 5, 20),
            docstatus=1,
            document_no=f"PRT-2355-{sufijo}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            is_return=True,
            reversal_of=original.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("40"),
            base_total=Decimal("40"),
            grand_total=Decimal("40"),
        )
        database.session.add(devolucion)
        database.session.flush()
        devolucion_item = PurchaseReceiptItem(
            purchase_receipt_id=devolucion.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("4"),
            qty_in_base_uom=Decimal("4"),
            uom=uom.code,
            rate=Decimal("10"),
            amount=Decimal("40"),
            base_amount=Decimal("40"),
            warehouse=warehouse.code,
        )
        database.session.add(devolucion_item)
        database.session.commit()
        devolucion_item_id = str(devolucion_item.id)
        with audit_actor(actor.id, actor.name), approved_execution(devolucion, actor.id):
            post_purchase_receipt(devolucion)
        database.session.commit()

        devolucion_id = str(devolucion.id)
        factura_id = str(factura.id)
        original_id = str(original.id)
        actor_id, actor_name = actor.id, actor.name
        usuario_id = str(actor.id)
        auth_version = actor.auth_version
        item_code = item.code
        supplier_id = str(supplier.id)
        database.session.remove()

    with app.app_context():
        devolucion_row = (
            database.session.execute(database.select(PurchaseReceiptReturnAllocation).filter_by(status="active"))
            .scalars()
            .all()
        )
        assert devolucion_row, "la devolución debe quedar con allocations activas"
        factura_row = database.session.get(PurchaseInvoice, factura_id)
        assert factura_row is not None and factura_row.docstatus == 1
        database.session.remove()

    return {
        "devolucion": devolucion_id,
        "factura": factura_id,
        "original": original_id,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "usuario_id": usuario_id,
        "auth_version": auth_version,
        "item_code": item_code,
        "devolucion_item": devolucion_item_id,
        "supplier_id": supplier_id,
    }


def _crear_nota_por_http(app, datos: dict[str, object]) -> str:
    """Crea la nota de crédito por devolución física con un POST real."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = datos["usuario_id"]
        session["_auth_version"] = datos["auth_version"]
        session["_fresh"] = True
    respuesta = client.post(
        "/buying/purchase-invoice/new",
        data={
            "company": "cacao",
            "supplier_id": datos["supplier_id"],
            "posting_date": "2026-05-25",
            "document_type": "purchase_credit_note",
            "credit_note_type": "physical_return",
            "from_receipt": datos["devolucion"],
            "item_code_0": datos["item_code"],
            "item_name_0": "Artículo",
            "qty_0": "4",
            "rate_0": "10",
            "uom_0": "UND",
            "source_type_0": "purchase_receipt",
            "source_id_0": datos["devolucion"],
            "source_item_id_0": datos["devolucion_item"],
        },
        follow_redirects=False,
    )
    if respuesta.status_code != 302:
        cuerpo = html.unescape(respuesta.get_data(as_text=True))
        raise AssertionError(f"el POST de creación no redirige ({respuesta.status_code}): {cuerpo[:4000]}")
    cuerpo = html.unescape(client.get(respuesta.headers["Location"]).get_data(as_text=True))
    assert "Factura de compra creada correctamente." in cuerpo, cuerpo[:4000]
    with app.app_context():
        nota = (
            database.session.execute(
                database.select(PurchaseInvoice)
                .filter_by(credit_note_type="physical_return", purchase_receipt_id=datos["devolucion"])
                .order_by(PurchaseInvoice.posting_date.desc())
            )
            .scalars()
            .first()
        )
        assert nota is not None, "el POST debe crear la nota física"
        assert nota.docstatus == 0
        nota_id = str(nota.id)
        database.session.remove()
    return nota_id


def test_post_http_de_nota_fisica_rechaza_devolucion_cancelada():
    """El POST completo de la nota no confirma contra una devolución cancelada en el intercalado."""
    url, name = _isolated_url()
    try:
        app = create_app(
            {
                **configuracion,
                "SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False),
                "SQLALCHEMY_ENGINE_OPTIONS": {
                    **configuracion.get("SQLALCHEMY_ENGINE_OPTIONS", {}),
                    "pool_size": 4,
                    "max_overflow": 0,
                },
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "WTF_CSRF_ENABLED": False,
                "TESTING": True,
                "SECRET_KEY": "test-2355-post",
                "MODO_ESCRITORIO": False,
            }
        )
        _seed(app)
        datos = _sembrar_cadena_posteada(app)
        nota_id = _crear_nota_por_http(app, datos)

        lock_adquirido = Event()
        post_bloqueado = Event()

        def cancelar_devolucion() -> str:
            with app.app_context():
                try:
                    devolucion = database.session.get(PurchaseReceipt, datos["devolucion"])
                    with (
                        audit_actor(datos["actor_id"], datos["actor_name"]),
                        approved_execution(devolucion, datos["actor_id"]),
                    ):
                        cancel_document(
                            devolucion,
                            reason="Cancelación concurrente con el POST de la nota",
                            actor_user_id=datos["actor_id"],
                            cancellation_date=date(2026, 5, 20),
                        )
                    lock_adquirido.set()
                    post_bloqueado.wait(timeout=30)
                    database.session.commit()
                    return "cancelada"
                except Exception as exc:  # pragma: no cover - diagnóstico del fallo
                    database.session.rollback()
                    return f"error: {exc}"
                finally:
                    lock_adquirido.set()
                    post_bloqueado.set()
                    database.session.remove()

        def postear_nota() -> str:
            assert lock_adquirido.wait(timeout=30), "la cancelación nunca tomó el lock"
            client = app.test_client()
            with client.session_transaction() as session:
                session["_user_id"] = datos["usuario_id"]
                session["_auth_version"] = datos["auth_version"]
                session["_fresh"] = True
            respuesta = client.post(f"/buying/purchase-invoice/{nota_id}/submit", follow_redirects=True)
            return html.unescape(respuesta.get_data(as_text=True))

        with ThreadPoolExecutor(max_workers=2) as trabajadores:
            futuro_cancelacion = trabajadores.submit(cancelar_devolucion)
            assert lock_adquirido.wait(timeout=30), "la cancelación nunca tomó el lock"
            futuro_post = trabajadores.submit(postear_nota)
            _esperar_bloqueo_de_fila(url, PurchaseReceipt.__tablename__)
            post_bloqueado.set()
            resultado_cancelacion = futuro_cancelacion.result(timeout=60)
            cuerpo_post = futuro_post.result(timeout=60)

        assert resultado_cancelacion == "cancelada", resultado_cancelacion
        assert RECHAZO in cuerpo_post, cuerpo_post[:4000]

        with app.app_context():
            nota = database.session.get(PurchaseInvoice, nota_id)
            assert nota is not None and nota.docstatus == 0, "la nota no debe contabilizarse"
            item_ids = [
                fila.id
                for fila in database.session.execute(
                    database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=nota_id)
                ).scalars()
            ]
            aplicaciones = (
                database.session.execute(
                    database.select(PurchaseCreditNoteAllocation).where(
                        PurchaseCreditNoteAllocation.credit_note_item_id.in_(item_ids)
                    )
                )
                .scalars()
                .all()
            )
            assert aplicaciones == [], "la nota cancelada no deja aplicaciones"
            asientos = database.session.execute(database.select(GLEntry).filter_by(voucher_id=nota_id)).scalars().all()
            assert asientos == [], "la nota rechazada no debe contabilizar GL"
            devolucion = database.session.get(PurchaseReceipt, datos["devolucion"])
            assert devolucion is not None and devolucion.docstatus == 2
            database.session.remove()
    finally:
        _drop(url, name)
