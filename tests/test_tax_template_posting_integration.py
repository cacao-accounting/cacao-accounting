# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2020: una plantilla con inactivo previo conserva total fiscal y GL."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from cacao_accounting.accounting_engine.document_builders import build_calculation_context
from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.posting_service import submit_document
from cacao_accounting.database import (
    Accounts,
    Book,
    GLEntry,
    Item,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    SalesInvoice,
    SalesInvoiceItem,
    Tax,
    TaxTemplate,
    TaxTemplateItem,
    UOM,
    User,
    database,
)
from cacao_accounting.fiscal_persistence_service import calculate_document_total_with_taxes
from cacao_accounting.internal_control_service import audit_actor
from cacao_accounting.tax_pricing_service import calculate_taxes


def _crear_plantilla(sufijo: str, template_type: str) -> TaxTemplate:
    """Crea IVA 10% aditivo, inactivo intermedio y retención 20% sobre total previo."""
    iva = database.session.execute(select(Accounts).filter_by(entity="cacao", code="2105")).scalar_one()
    retencion_cuenta = database.session.execute(select(Accounts).filter_by(entity="cacao", code="2199")).scalar_one()
    if database.session.get(Tax, f"IVA-{sufijo}") is None:
        database.session.add_all(
            [
                Tax(
                    id=f"IVA-{sufijo}",
                    name="IVA",
                    rate=10,
                    tax_type="percentage",
                    applies_to="both",
                    is_active=True,
                    account_id=iva.id,
                ),
                Tax(
                    id=f"INA-{sufijo}",
                    name="Impuesto inactivo",
                    rate=5,
                    tax_type="percentage",
                    applies_to="both",
                    is_active=False,
                    account_id=iva.id,
                ),
                Tax(
                    id=f"WHT-{sufijo}",
                    name="Retención",
                    rate=20,
                    tax_type="percentage",
                    applies_to="both",
                    is_active=True,
                    account_id=retencion_cuenta.id,
                    is_charge=False,
                ),
            ]
        )
    plantilla = TaxTemplate(
        name=f"Plantilla {template_type} {sufijo}",
        company="cacao",
        template_type=template_type,
        currency="NIO",
        is_active=True,
    )
    database.session.add(plantilla)
    database.session.flush()
    database.session.add_all(
        [
            TaxTemplateItem(
                tax_template_id=plantilla.id,
                tax_id=f"IVA-{sufijo}",
                sequence=10,
                calculation_base="net_document",
                behavior="additive",
                is_inclusive=False,
            ),
            TaxTemplateItem(
                tax_template_id=plantilla.id,
                tax_id=f"INA-{sufijo}",
                sequence=20,
                calculation_base="net_document",
                behavior="additive",
                is_inclusive=False,
            ),
            TaxTemplateItem(
                tax_template_id=plantilla.id,
                tax_id=f"WHT-{sufijo}",
                sequence=30,
                calculation_base="previous_total",
                behavior="deductive",
                is_inclusive=False,
            ),
        ]
    )
    database.session.flush()
    return plantilla


def _asientos(voucher_id: str, ledger_id: str) -> dict[str, tuple[Decimal, Decimal]]:
    """Devuelve débitos y créditos por cuenta para un libro."""
    filas = database.session.execute(
        select(GLEntry).where(GLEntry.voucher_id == voucher_id, GLEntry.ledger_id == ledger_id)
    ).scalars()
    return {fila.account_code: (Decimal(fila.debit), Decimal(fila.credit)) for fila in filas}


def test_plantilla_con_inactivo_previo_conserva_total_y_gl(entorno_contable_aislado):
    """El total persistido y el asiento coinciden en venta y compra."""
    app = entorno_contable_aislado.app
    with app.app_context():
        libros = (
            database.session.execute(select(Book.id).where(Book.entity == "cacao", Book.status == "activo")).scalars().all()
        )
        assert len(libros) >= 2
        sufijo = uuid4().hex[:6]
        database.session.add(
            Accounts(
                entity="cacao",
                code="2199",
                name="Retenciones por pagar",
                classification="liability",
                account_type="tax",
            )
        )
        database.session.flush()
        cliente = database.session.execute(select(Party).filter_by(code="CLI001")).scalar_one()
        proveedor = database.session.execute(select(Party).filter_by(code="PRV001")).scalar_one()
        actor = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        item = database.session.execute(select(Item).filter_by(code="ART01")).scalar_one()
        uom = database.session.execute(select(UOM).filter_by(code="UND")).scalar_one()
        ingreso = database.session.execute(select(Accounts).filter_by(entity="cacao", code="4101")).scalar_one()
        gasto = database.session.execute(select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
        plantilla_venta = _crear_plantilla(sufijo, "selling")
        plantilla_compra = _crear_plantilla(sufijo, "buying")

        venta = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_date=date(2026, 5, 15),
            document_no=f"PV-{sufijo}",
            customer_id=cliente.id,
            customer_name=cliente.name,
            tax_template_id=plantilla_venta.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        compra = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_no=f"PC-{sufijo}",
            document_type="purchase_invoice",
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
            tax_template_id=plantilla_compra.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add_all([venta, compra])
        database.session.flush()
        item_venta = SalesInvoiceItem(
            sales_invoice_id=venta.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom=uom.code,
            rate=Decimal("100"),
            amount=Decimal("100"),
            base_amount=Decimal("100"),
            income_account_id=ingreso.id,
        )
        item_compra = PurchaseInvoiceItem(
            purchase_invoice_id=compra.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom=uom.code,
            rate=Decimal("100"),
            amount=Decimal("100"),
            base_amount=Decimal("100"),
            expense_account_id=gasto.id,
        )
        database.session.add_all([item_venta, item_compra])
        database.session.flush()

        total_venta = calculate_document_total_with_taxes(venta, Decimal("100"), [item_venta])
        total_compra = calculate_document_total_with_taxes(compra, Decimal("100"), [item_compra])
        assert total_venta == Decimal("88")
        assert total_compra == Decimal("88")

        contexto_venta = build_calculation_context(venta)
        retencion_venta = next(regla for regla in contexto_venta.tax_rules if regla.rule_id == f"WHT-{sufijo}")
        assert retencion_venta.base_mode == "accumulated"
        assert retencion_venta.tax_type == "withholding"
        assert "iva" in retencion_venta.include_concepts

        venta.total = venta.base_total = venta.grand_total = venta.base_grand_total = total_venta
        venta.outstanding_amount = venta.base_outstanding_amount = total_venta
        compra.total = compra.base_total = compra.grand_total = compra.base_grand_total = total_compra
        compra.outstanding_amount = compra.base_outstanding_amount = total_compra
        database.session.commit()

        with audit_actor(actor.id, actor.name):
            with approved_execution(venta, actor.id):
                submit_document(venta)
            with approved_execution(compra, actor.id):
                submit_document(compra)
        database.session.commit()

        assert venta.docstatus == 1
        assert compra.docstatus == 1
        assert venta.grand_total == Decimal("88")
        assert compra.grand_total == Decimal("88")

        esperado_venta = {
            "4101": (Decimal("0"), Decimal("100")),
            "2105": (Decimal("0"), Decimal("10")),
            "2199": (Decimal("22"), Decimal("0")),
            "1105": (Decimal("88"), Decimal("0")),
        }
        esperado_compra = {
            "5201": (Decimal("100"), Decimal("0")),
            "2105": (Decimal("10"), Decimal("0")),
            "2199": (Decimal("0"), Decimal("22")),
            "2101": (Decimal("0"), Decimal("88")),
        }
        for libro in libros:
            assert _asientos(venta.id, libro) == esperado_venta
            assert _asientos(compra.id, libro) == esperado_compra


def _crear_plantilla_inclusiva(sufijo: str, template_type: str) -> TaxTemplate:
    """Crea inactivo 10% seguido de un activo 20% inclusivo y deductivo."""
    iva = database.session.execute(select(Accounts).filter_by(entity="cacao", code="2105")).scalar_one()
    retencion_cuenta = database.session.execute(select(Accounts).filter_by(entity="cacao", code="2199")).scalar_one()
    database.session.add_all(
        [
            Tax(
                id=f"INA-INC-{template_type}-{sufijo}",
                name="Inactivo inclusivo",
                rate=10,
                tax_type="percentage",
                applies_to="both",
                is_active=False,
                account_id=iva.id,
            ),
            Tax(
                id=f"INC-{template_type}-{sufijo}",
                name="Retención inclusiva",
                rate=20,
                tax_type="percentage",
                applies_to="both",
                is_active=True,
                account_id=retencion_cuenta.id,
                is_charge=False,
            ),
        ]
    )
    plantilla = TaxTemplate(
        name=f"Plantilla inclusiva {template_type} {sufijo}",
        company="cacao",
        template_type=template_type,
        currency="NIO",
        is_active=True,
    )
    database.session.add(plantilla)
    database.session.flush()
    database.session.add_all(
        [
            TaxTemplateItem(
                tax_template_id=plantilla.id,
                tax_id=f"INA-INC-{template_type}-{sufijo}",
                sequence=10,
                calculation_base="net_document",
                behavior="additive",
                is_inclusive=False,
            ),
            TaxTemplateItem(
                tax_template_id=plantilla.id,
                tax_id=f"INC-{template_type}-{sufijo}",
                sequence=20,
                calculation_base="previous_total",
                behavior="deductive",
                is_inclusive=True,
            ),
        ]
    )
    database.session.flush()
    return plantilla


def test_plantilla_inclusiva_deductiva_con_inactivo_previo(entorno_contable_aislado):
    """El caso inclusivo/deductivo conserva cálculo, total persistido y GL."""
    app = entorno_contable_aislado.app
    with app.app_context():
        libros = (
            database.session.execute(select(Book.id).where(Book.entity == "cacao", Book.status == "activo")).scalars().all()
        )
        sufijo = uuid4().hex[:6]
        database.session.add(
            Accounts(
                entity="cacao",
                code="2199",
                name="Retenciones por pagar",
                classification="liability",
                account_type="tax",
                active=True,
                enabled=True,
                group=False,
            )
        )
        database.session.flush()
        cliente = database.session.execute(select(Party).filter_by(code="CLI001")).scalar_one()
        proveedor = database.session.execute(select(Party).filter_by(code="PRV001")).scalar_one()
        actor = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        item = database.session.execute(select(Item).filter_by(code="ART01")).scalar_one()
        uom = database.session.execute(select(UOM).filter_by(code="UND")).scalar_one()
        ingreso = database.session.execute(select(Accounts).filter_by(entity="cacao", code="4101")).scalar_one()
        gasto = database.session.execute(select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
        plantilla_venta = _crear_plantilla_inclusiva(sufijo, "selling")
        plantilla_compra = _crear_plantilla_inclusiva(sufijo, "buying")

        venta = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_date=date(2026, 5, 15),
            document_no=f"PVI-{sufijo}",
            customer_id=cliente.id,
            customer_name=cliente.name,
            tax_template_id=plantilla_venta.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        compra = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_no=f"PCI-{sufijo}",
            document_type="purchase_invoice",
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
            tax_template_id=plantilla_compra.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add_all([venta, compra])
        database.session.flush()
        item_venta = SalesInvoiceItem(
            sales_invoice_id=venta.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom=uom.code,
            rate=Decimal("100"),
            amount=Decimal("100"),
            base_amount=Decimal("100"),
            income_account_id=ingreso.id,
        )
        item_compra = PurchaseInvoiceItem(
            purchase_invoice_id=compra.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom=uom.code,
            rate=Decimal("100"),
            amount=Decimal("100"),
            base_amount=Decimal("100"),
            expense_account_id=gasto.id,
        )
        database.session.add_all([item_venta, item_compra])
        database.session.flush()

        total_venta = calculate_document_total_with_taxes(venta, Decimal("100"), [item_venta])
        total_compra = calculate_document_total_with_taxes(compra, Decimal("100"), [item_compra])
        assert total_venta == Decimal("100")
        assert total_compra == Decimal("100")

        venta._tax_items = [item_venta]
        compra._tax_items = [item_compra]
        resultado_venta = calculate_taxes(venta, plantilla_venta.id)
        resultado_compra = calculate_taxes(compra, plantilla_compra.id)
        assert [line.tax_id for line in resultado_venta.lines] == [f"INC-selling-{sufijo}"]
        assert [line.tax_id for line in resultado_compra.lines] == [f"INC-buying-{sufijo}"]
        assert resultado_venta.lines[0].amount == Decimal("16.6667")
        assert resultado_compra.lines[0].amount == Decimal("16.6667")
        assert resultado_venta.lines[0].is_inclusive is True
        assert resultado_compra.lines[0].is_inclusive is True
        assert resultado_venta.payable_delta == Decimal("0")

        contexto_venta = build_calculation_context(venta)
        contexto_compra = build_calculation_context(compra)
        regla_venta = next(rule for rule in contexto_venta.tax_rules if rule.rule_id == f"INC-selling-{sufijo}")
        regla_compra = next(rule for rule in contexto_compra.tax_rules if rule.rule_id == f"INC-buying-{sufijo}")
        assert regla_venta.base_mode == "accumulated"
        assert regla_compra.base_mode == "accumulated"
        assert regla_venta.included_in_price is True
        assert regla_compra.included_in_price is True

        venta.total = venta.base_total = venta.grand_total = venta.base_grand_total = total_venta
        venta.outstanding_amount = venta.base_outstanding_amount = total_venta
        compra.total = compra.base_total = compra.grand_total = compra.base_grand_total = total_compra
        compra.outstanding_amount = compra.base_outstanding_amount = total_compra
        database.session.commit()

        with audit_actor(actor.id, actor.name):
            with approved_execution(venta, actor.id):
                submit_document(venta)
            with approved_execution(compra, actor.id):
                submit_document(compra)
        database.session.commit()

        venta_id, compra_id = venta.id, compra.id
        database.session.remove()
        venta_persistida = database.session.get(SalesInvoice, venta_id)
        compra_persistida = database.session.get(PurchaseInvoice, compra_id)
        assert venta_persistida is not None
        assert compra_persistida is not None
        assert venta_persistida.docstatus == 1
        assert compra_persistida.docstatus == 1
        assert venta_persistida.grand_total == Decimal("100.0000")
        assert compra_persistida.grand_total == Decimal("100.0000")

        esperado_venta = {
            "4101": (Decimal("0"), Decimal("100")),
            "1105": (Decimal("100"), Decimal("0")),
        }
        esperado_compra = {
            "5201": (Decimal("100"), Decimal("0")),
            "2101": (Decimal("0"), Decimal("100")),
        }
        for libro in libros:
            assert _asientos(venta_id, libro) == esperado_venta
            assert _asientos(compra_id, libro) == esperado_compra
