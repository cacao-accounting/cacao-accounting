# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2127: la reclasificación 2-way se atribuye por artículo."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.accounting_engine.document_builders import _subtract_late_receipt_reclassifications
from cacao_accounting.database import (
    Item,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseInvoiceReceiptAllocation,
    PurchaseReceipt,
    PurchaseReceiptItem,
    database,
)

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
        receipts, item_ids = _sembrar_recepciones(suffix, [(codes[0], "50"), (codes[1], "100")])
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
