# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2127: la reclasificación 2-way se atribuye por artículo."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.accounting_engine.document_builders import (
    _late_two_way_invoice_amounts,
    _subtract_late_receipt_reclassifications,
)
from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.posting_service import post_purchase_invoice, post_purchase_receipt
from cacao_accounting.database import (
    Accounts,
    CompanyDefaultAccount,
    GLEntry,
    Item,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseInvoiceReceiptAllocation,
    PurchaseMatchingConfig,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    UOM,
    User,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.internal_control_service import audit_actor

FECHA = date(2026, 5, 15)


def _sembrar_articulos(suffix: str, codes: list[str]) -> None:
    """Crea los artículos que participan en las recepciones."""
    database.session.add_all(
        [
            Item(
                code=code,
                name=f"Artículo {code}",
                item_type="goods",
                is_stock_item=False,
                default_uom="UND",
            )
            for code in codes
        ]
    )
    database.session.flush()


def _sembrar_recepciones(suffix: str, lineas: list[tuple[str, str]]) -> tuple[list[PurchaseReceipt], dict[str, str]]:
    """Crea recepciones previas y devuelve el id de línea de cada artículo."""
    receipts: list[PurchaseReceipt] = []
    item_ids: dict[str, str] = {}
    for index, (item_code, amount) in enumerate(lineas):
        receipt = PurchaseReceipt(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"PR-REC-{suffix}-{index}",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(receipt)
        database.session.flush()
        receipt_item = PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code=item_code,
            item_name=item_code,
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="UND",
            rate=Decimal(amount),
            amount=Decimal(amount),
        )
        database.session.add(receipt_item)
        database.session.flush()
        receipts.append(receipt)
        item_ids[item_code] = receipt_item.id
    return receipts, item_ids


def _sembrar_factura(suffix: str, codes: list[str], supplier_id: str) -> dict[str, str]:
    """Crea la factura cuyas líneas respaldan las asignaciones auditables."""
    factura = PurchaseInvoice(
        company="cacao",
        posting_date=FECHA,
        docstatus=1,
        document_no=f"PI-REC-{suffix}",
        document_type="purchase_invoice",
        supplier_id=supplier_id,
        supplier_name="Proveedor",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        grand_total=Decimal("300"),
    )
    database.session.add(factura)
    database.session.flush()
    invoice_items: dict[str, str] = {}
    for code in codes:
        item = PurchaseInvoiceItem(
            purchase_invoice_id=factura.id,
            item_code=code,
            item_name=code,
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="UND",
            rate=Decimal("100"),
            amount=Decimal("100"),
        )
        database.session.add(item)
        database.session.flush()
        invoice_items[code] = item.id
    return invoice_items


def _asignacion(
    invoice_item_id: str, receipt_item_id: str, amount: str, status: str = "active"
) -> PurchaseInvoiceReceiptAllocation:
    """Construye una asignación factura-recepción con el estado indicado."""
    return PurchaseInvoiceReceiptAllocation(
        invoice_item_id=invoice_item_id,
        receipt_item_id=receipt_item_id,
        company="cacao",
        qty_in_base_uom=Decimal("1"),
        receipt_amount=Decimal(amount),
        receipt_base_amount=Decimal(amount),
        invoice_amount=Decimal(amount),
        invoice_base_amount=Decimal(amount),
        price_variance_base=Decimal("0"),
        exchange_variance_base=Decimal("0"),
        transaction_currency="NIO",
        base_currency="NIO",
        receipt_exchange_rate=Decimal("1"),
        invoice_exchange_rate=Decimal("1"),
        status=status,
    )


def _supplier_id(app) -> str:
    """Obtiene el tercero sembrado dentro de un contexto fresco."""
    with app.app_context():
        return str(database.session.execute(database.select(Party.id).filter_by(code="PRV001")).scalar_one())


def test_la_reclasificacion_previa_no_se_resta_dos_veces(app, entorno_contable):
    """Cada crédito de recepción descuenta solo su artículo, no toda la cuenta."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        codes = [f"ART-A-{suffix}", f"ART-B-{suffix}"]
        _sembrar_articulos(suffix, codes)
        receipts, _item_ids = _sembrar_recepciones(suffix, [(codes[0], "50"), (codes[1], "100")])
        database.session.commit()
        current = receipts[0]
        amounts = {codes[0]: Decimal("100"), codes[1]: Decimal("200")}
        posting_dates = {code: date(2026, 5, 1) for code in codes}

        _subtract_late_receipt_reclassifications(current, amounts, posting_dates, receipts)

        assert amounts == {codes[0]: Decimal("50"), codes[1]: Decimal("100")}


def test_las_asignaciones_activas_se_acumulan_y_las_canceladas_no_descuentan(app, entorno_contable):
    """La evidencia persistida descuenta cada línea una sola vez y por su artículo."""
    suffix = uuid4().hex[:8]
    supplier_id = _supplier_id(app)
    with app.app_context():
        codes = [f"ART-A-{suffix}", f"ART-B-{suffix}"]
        _sembrar_articulos(suffix, codes)
        receipts, item_ids = _sembrar_recepciones(suffix, [(codes[0], "70"), (codes[1], "130")])
        invoice_items = _sembrar_factura(suffix, codes, supplier_id)
        database.session.add_all(
            [
                _asignacion(invoice_items[codes[0]], item_ids[codes[0]], "20"),
                _asignacion(invoice_items[codes[0]], item_ids[codes[0]], "30"),
                _asignacion(invoice_items[codes[1]], item_ids[codes[1]], "100"),
                _asignacion(invoice_items[codes[1]], item_ids[codes[1]], "40", status="cancelled"),
            ]
        )
        database.session.commit()
        amounts = {codes[0]: Decimal("100"), codes[1]: Decimal("200")}
        posting_dates = {code: date(2026, 5, 1) for code in codes}

        _subtract_late_receipt_reclassifications(receipts[0], amounts, posting_dates, receipts)

        assert amounts == {codes[0]: Decimal("50"), codes[1]: Decimal("100")}


def test_asignacion_de_otra_factura_no_descuenta_la_reclasificacion(app, entorno_contable):
    """Solo las asignaciones de las facturas 2-way integradas descuentan."""
    suffix = uuid4().hex[:8]
    supplier_id = _supplier_id(app)
    with app.app_context():
        code = f"ART-X-{suffix}"
        _sembrar_articulos(suffix, [code])
        receipts, item_ids = _sembrar_recepciones(suffix, [(code, "100")])
        invoice_items = _sembrar_factura(suffix, [code], supplier_id)
        otra_factura = _sembrar_factura(f"OTRA-{suffix}", [code], supplier_id)
        database.session.add_all(
            [
                _asignacion(invoice_items[code], item_ids[code], "20"),
                _asignacion(otra_factura[code], item_ids[code], "80"),
            ]
        )
        database.session.commit()
        amounts = {code: Decimal("100")}
        posting_dates = {code: date(2026, 5, 1)}

        _subtract_late_receipt_reclassifications(
            receipts[0],
            amounts,
            posting_dates,
            receipts,
            invoice_item_ids={invoice_items[code]},
        )

        assert amounts == {code: Decimal("80")}


def _preparar_ciclo_real(app):
    """Publica una factura 2-way y dos recepciones sucesivas con GL real."""
    with app.app_context():
        defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        bridge = database.session.execute(
            database.select(Accounts).filter_by(entity="cacao", code="2103")
        ).scalar_one_or_none()
        if bridge is None:
            bridge = Accounts(
                entity="cacao", code="2103", name="Puente compras", classification="liability", account_type="bridge"
            )
            database.session.add(bridge)
            database.session.flush()
        inventory = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1109")).scalar_one()
        defaults.bridge_account_id = bridge.id
        matching = database.session.execute(
            database.select(PurchaseMatchingConfig).filter_by(company="cacao")
        ).scalar_one_or_none()
        if matching is None:
            matching = PurchaseMatchingConfig(company="cacao", matching_type="2-way", auto_reconcile=False)
            database.session.add(matching)
        else:
            matching.matching_type = "2-way"
            matching.require_purchase_order = False
            matching.auto_reconcile = False
        mapping = database.session.execute(
            database.select(WarehouseCompanyAccount).filter_by(warehouse_code="BOD01", company="cacao")
        ).scalar_one_or_none()
        if mapping is None:
            database.session.add(
                WarehouseCompanyAccount(warehouse_code="BOD01", company="cacao", inventory_account_id=inventory.id)
            )
        else:
            mapping.inventory_account_id = inventory.id

        supplier = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
        uom = database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one()
        warehouse = database.session.execute(database.select(Warehouse).filter_by(code="BOD01", company="cacao")).scalar_one()
        suffix = uuid4().hex[:8]
        order = PurchaseOrder(
            company="cacao",
            document_no=f"PO-LATE-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            posting_date=date(2026, 5, 1),
            docstatus=1,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(order)
        database.session.flush()
        database.session.add(
            PurchaseOrderItem(
                purchase_order_id=order.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom=uom.code,
                rate=Decimal("100"),
                amount=Decimal("100"),
            )
        )
        invoice = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 5),
            docstatus=1,
            document_no=f"PI-LATE-{suffix}",
            document_type="purchase_invoice",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            purchase_order_id=order.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("100"),
            base_total=Decimal("100"),
            grand_total=Decimal("100"),
            outstanding_amount=Decimal("100"),
            base_outstanding_amount=Decimal("100"),
        )
        database.session.add(invoice)
        database.session.flush()
        database.session.add(
            PurchaseInvoiceItem(
                purchase_invoice_id=invoice.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom=uom.code,
                rate=Decimal("100"),
                amount=Decimal("100"),
            )
        )
        receipts = []
        for index, amount in enumerate(("50", "50"), start=1):
            receipt = PurchaseReceipt(
                company="cacao",
                posting_date=date(2026, 5, 10 + index),
                docstatus=1,
                document_no=f"PR-LATE-{suffix}-{index}",
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                purchase_order_id=order.id,
                transaction_currency="NIO",
                base_currency="NIO",
                exchange_rate=Decimal("1"),
                total=Decimal(amount),
                base_total=Decimal(amount),
                grand_total=Decimal(amount),
            )
            database.session.add(receipt)
            database.session.flush()
            database.session.add(
                PurchaseReceiptItem(
                    purchase_receipt_id=receipt.id,
                    item_code=item.code,
                    item_name=item.name,
                    qty=Decimal("0.5"),
                    qty_in_base_uom=Decimal("0.5"),
                    uom=uom.code,
                    rate=Decimal("100"),
                    amount=Decimal(amount),
                    base_amount=Decimal(amount),
                    warehouse=warehouse.code,
                )
            )
            receipts.append(receipt)
        database.session.commit()
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        with audit_actor(actor.id, actor.name):
            with approved_execution(invoice, actor.id):
                post_purchase_invoice(invoice)
            database.session.commit()
            for receipt in receipts:
                with approved_execution(receipt, actor.id):
                    post_purchase_receipt(receipt)
                database.session.commit()
        return {
            "invoice": invoice.id,
            "receipts": [receipt.id for receipt in receipts],
            "item": item.code,
        }


def _gasto_por_libro(voucher_id: str, field: str) -> dict[str, Decimal]:
    """Suma debe o haber de la cuenta de gasto por libro."""
    rows = database.session.execute(
        database.select(GLEntry).where(GLEntry.voucher_id == voucher_id, GLEntry.account_code == "5201")
    ).scalars()
    totals: dict[str, Decimal] = {}
    for row in rows:
        totals[row.ledger_id] = totals.get(row.ledger_id, Decimal("0")) + getattr(row, field)
    return totals


def test_ciclo_real_reconcilia_reclasificacion_con_gl(entorno_contable_aislado):
    """Las recepciones reales y sus créditos GL cuadran con la factura 2-way."""
    app = entorno_contable_aislado.app
    ids = _preparar_ciclo_real(app)
    with app.app_context():
        receipt1, receipt2 = ids["receipts"]
        gasto_factura = _gasto_por_libro(ids["invoice"], "debit")
        credito_1 = _gasto_por_libro(receipt1, "credit")
        credito_2 = _gasto_por_libro(receipt2, "credit")
        assert gasto_factura
        assert set(credito_1) == set(credito_2) == set(gasto_factura)
        for libro, importe in gasto_factura.items():
            assert importe == Decimal("100.0000")
            assert credito_1[libro] == Decimal("50.0000")
            assert credito_2[libro] == Decimal("50.0000")
            assert credito_1[libro] + credito_2[libro] == importe

        pendiente = _late_two_way_invoice_amounts(database.session.get(PurchaseReceipt, receipt2))
        assert pendiente[ids["item"]] == Decimal("50.0000")


def test_la_asignacion_activa_no_excede_el_pendiente_del_articulo(app, entorno_contable):
    """Una asignación mayor al saldo disponible no genera importe negativo."""
    suffix = uuid4().hex[:8]
    supplier_id = _supplier_id(app)
    with app.app_context():
        code = f"ART-C-{suffix}"
        _sembrar_articulos(suffix, [code])
        receipts, item_ids = _sembrar_recepciones(suffix, [(code, "300")])
        invoice_items = _sembrar_factura(suffix, [code], supplier_id)
        database.session.add(_asignacion(invoice_items[code], item_ids[code], "300"))
        database.session.commit()
        amounts = {code: Decimal("100")}
        posting_dates = {code: date(2026, 5, 1)}

        _subtract_late_receipt_reclassifications(receipts[0], amounts, posting_dates, receipts)

        assert amounts == {code: Decimal("0")}


def test_factura_posterior_a_recepcion_no_descuenta_su_reclasificacion(app, entorno_contable):
    """I1/R1/I2/R2: I2 no pudo reclasificar el GL de R1 al calcular R2."""
    suffix = uuid4().hex[:8]
    supplier_id = _supplier_id(app)
    with app.app_context():
        code = f"ART-T-{suffix}"
        _sembrar_articulos(suffix, [code])
        supplier = database.session.get(Party, supplier_id)
        uom = database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one()
        order = PurchaseOrder(
            company="cacao",
            document_no=f"PO-T-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            posting_date=date(2026, 5, 1),
            docstatus=1,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(order)
        database.session.flush()
        database.session.add(
            PurchaseOrderItem(
                purchase_order_id=order.id,
                item_code=code,
                item_name=code,
                qty=Decimal("2"),
                qty_in_base_uom=Decimal("2"),
                uom=uom.code,
                rate=Decimal("100"),
                amount=Decimal("200"),
            )
        )

        def crear_factura(numero: str, fecha: date) -> tuple[PurchaseInvoice, PurchaseInvoiceItem]:
            factura = PurchaseInvoice(
                company="cacao",
                posting_date=fecha,
                docstatus=1,
                document_no=f"PI-T-{suffix}-{numero}",
                document_type="purchase_invoice",
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                purchase_order_id=order.id,
                transaction_currency="NIO",
                base_currency="NIO",
                exchange_rate=Decimal("1"),
                grand_total=Decimal("100"),
            )
            database.session.add(factura)
            database.session.flush()
            linea = PurchaseInvoiceItem(
                purchase_invoice_id=factura.id,
                item_code=code,
                item_name=code,
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom=uom.code,
                rate=Decimal("100"),
                amount=Decimal("100"),
            )
            database.session.add(linea)
            database.session.flush()
            return factura, linea

        def crear_recepcion(numero: str, fecha: date) -> tuple[PurchaseReceipt, PurchaseReceiptItem]:
            recepcion = PurchaseReceipt(
                company="cacao",
                posting_date=fecha,
                docstatus=1,
                document_no=f"PR-T-{suffix}-{numero}",
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                purchase_order_id=order.id,
                transaction_currency="NIO",
                base_currency="NIO",
                exchange_rate=Decimal("1"),
            )
            database.session.add(recepcion)
            database.session.flush()
            linea = PurchaseReceiptItem(
                purchase_receipt_id=recepcion.id,
                item_code=code,
                item_name=code,
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom=uom.code,
                rate=Decimal("100"),
                amount=Decimal("100"),
            )
            database.session.add(linea)
            database.session.flush()
            return recepcion, linea

        invoice1, invoice_item1 = crear_factura("I1", date(2026, 5, 2))
        receipt1, receipt_item1 = crear_recepcion("R1", date(2026, 5, 5))
        invoice2, invoice_item2 = crear_factura("I2", date(2026, 5, 10))
        receipt2, _ = crear_recepcion("R2", date(2026, 5, 15))
        database.session.add_all(
            [
                _asignacion(invoice_item1.id, receipt_item1.id, "100"),
                _asignacion(invoice_item2.id, receipt_item1.id, "100"),
            ]
        )
        database.session.commit()

        pendiente = _late_two_way_invoice_amounts(database.session.get(PurchaseReceipt, receipt2.id))

        assert invoice1.posting_date < receipt1.posting_date < invoice2.posting_date < receipt2.posting_date
        assert pendiente[code] == Decimal("100.0000")


def _preparar_ciclo_temporal_real(app):
    """Publica I1/R1/I2/R2 con GL real y siembra una asignación tardía inválida."""
    with app.app_context():
        defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalar_one()
        bridge = database.session.execute(
            database.select(Accounts).filter_by(entity="cacao", code="2103")
        ).scalar_one_or_none()
        if bridge is None:
            bridge = Accounts(
                entity="cacao", code="2103", name="Puente compras temporal", classification="liability", account_type="bridge"
            )
            database.session.add(bridge)
            database.session.flush()
        defaults.bridge_account_id = bridge.id
        matching = database.session.execute(
            database.select(PurchaseMatchingConfig).filter_by(company="cacao")
        ).scalar_one_or_none()
        if matching is None:
            matching = PurchaseMatchingConfig(company="cacao", matching_type="2-way", auto_reconcile=False)
            database.session.add(matching)
        else:
            matching.matching_type = "2-way"
            matching.require_purchase_order = False
            matching.auto_reconcile = False
        mapping = database.session.execute(
            database.select(WarehouseCompanyAccount).filter_by(warehouse_code="BOD01", company="cacao")
        ).scalar_one_or_none()
        if mapping is None:
            inventory = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1109")).scalar_one()
            database.session.add(
                WarehouseCompanyAccount(warehouse_code="BOD01", company="cacao", inventory_account_id=inventory.id)
            )

        supplier = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
        uom = database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one()
        warehouse = database.session.execute(database.select(Warehouse).filter_by(code="BOD01", company="cacao")).scalar_one()
        suffix = uuid4().hex[:8]
        order = PurchaseOrder(
            company="cacao",
            document_no=f"PO-TEMP-{suffix}",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            posting_date=date(2026, 5, 1),
            docstatus=1,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(order)
        database.session.flush()
        database.session.add(
            PurchaseOrderItem(
                purchase_order_id=order.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("2"),
                qty_in_base_uom=Decimal("2"),
                uom=uom.code,
                rate=Decimal("100"),
                amount=Decimal("200"),
            )
        )

        def crear_factura(dia: int, numero: str) -> tuple[PurchaseInvoice, PurchaseInvoiceItem]:
            factura = PurchaseInvoice(
                company="cacao",
                posting_date=date(2026, 5, dia),
                docstatus=1,
                document_no=f"PI-TEMP-{suffix}-{numero}",
                document_type="purchase_invoice",
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                purchase_order_id=order.id,
                transaction_currency="NIO",
                base_currency="NIO",
                exchange_rate=Decimal("1"),
                total=Decimal("100"),
                base_total=Decimal("100"),
                grand_total=Decimal("100"),
                outstanding_amount=Decimal("100"),
                base_outstanding_amount=Decimal("100"),
            )
            database.session.add(factura)
            database.session.flush()
            linea = PurchaseInvoiceItem(
                purchase_invoice_id=factura.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom=uom.code,
                rate=Decimal("100"),
                amount=Decimal("100"),
            )
            database.session.add(linea)
            database.session.flush()
            return factura, linea

        def crear_recepcion(dia: int, numero: str) -> tuple[PurchaseReceipt, PurchaseReceiptItem]:
            recepcion = PurchaseReceipt(
                company="cacao",
                posting_date=date(2026, 5, dia),
                docstatus=1,
                document_no=f"PR-TEMP-{suffix}-{numero}",
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                purchase_order_id=order.id,
                transaction_currency="NIO",
                base_currency="NIO",
                exchange_rate=Decimal("1"),
                total=Decimal("100"),
                base_total=Decimal("100"),
                grand_total=Decimal("100"),
            )
            database.session.add(recepcion)
            database.session.flush()
            linea = PurchaseReceiptItem(
                purchase_receipt_id=recepcion.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom=uom.code,
                rate=Decimal("100"),
                amount=Decimal("100"),
                base_amount=Decimal("100"),
                warehouse=warehouse.code,
            )
            database.session.add(linea)
            database.session.flush()
            return recepcion, linea

        invoice1, invoice_item1 = crear_factura(2, "I1")
        receipt1, receipt_item1 = crear_recepcion(5, "R1")
        invoice2, invoice_item2 = crear_factura(10, "I2")
        receipt2, _receipt_item2 = crear_recepcion(15, "R2")
        database.session.commit()

        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        with audit_actor(actor.id, actor.name):
            with approved_execution(invoice1, actor.id):
                post_purchase_invoice(invoice1)
            database.session.commit()
            with approved_execution(receipt1, actor.id):
                post_purchase_receipt(receipt1)
            database.session.commit()
            with approved_execution(invoice2, actor.id):
                post_purchase_invoice(invoice2)
            database.session.commit()
            with approved_execution(receipt2, actor.id):
                post_purchase_receipt(receipt2)
            database.session.commit()

        # Asignación tardía: I2 se contabilizó después de R1, por lo que no
        # pudo originar el crédito GL que esa recepción ya había publicado.
        database.session.add(_asignacion(invoice_item2.id, receipt_item1.id, "100"))
        database.session.commit()
        return {
            "invoices": [invoice1.id, invoice2.id],
            "receipts": [receipt1.id, receipt2.id],
            "item": item.code,
            "late_invoice_item": invoice_item2.id,
            "early_invoice_item": invoice_item1.id,
        }


def _movimiento_por_libro(voucher_ids: list[str], field: str) -> dict[str, Decimal]:
    """Suma debe o haber de todas las cuentas de un conjunto de comprobantes."""
    entries = database.session.execute(database.select(GLEntry).where(GLEntry.voucher_id.in_(voucher_ids))).scalars()
    totals: dict[str, Decimal] = {}
    for entry in entries:
        totals[entry.ledger_id] = totals.get(entry.ledger_id, Decimal("0")) + getattr(entry, field)
    return totals


def test_ciclo_temporal_reconcilia_reclasificacion_con_gl(entorno_contable_aislado):
    """El GL por libro y el saldo 2-way solo descuentan lo contabilizado en cada fecha."""
    app = entorno_contable_aislado.app
    ids = _preparar_ciclo_temporal_real(app)
    with app.app_context():
        debitos = _movimiento_por_libro(ids["invoices"], "debit")
        creditos = _movimiento_por_libro(ids["receipts"], "credit")
        gasto_1 = _gasto_por_libro(ids["receipts"][0], "credit")
        gasto_2 = _gasto_por_libro(ids["receipts"][1], "credit")

        assert debitos and creditos
        assert set(debitos) == set(creditos) == set(gasto_1) == set(gasto_2)
        for libro in debitos:
            # I1 carga gasto e I2 carga el puente porque R1 ya estaba contabilizada.
            assert debitos[libro] == Decimal("200.00000000")
            assert creditos[libro] == Decimal("200.00000000")
            assert gasto_1[libro] == Decimal("100.00000000")
            assert gasto_2[libro] == Decimal("100.00000000")

        pendiente = _late_two_way_invoice_amounts(database.session.get(PurchaseReceipt, ids["receipts"][1]))
        assert pendiente[ids["item"]] == gasto_2[next(iter(gasto_2))]
