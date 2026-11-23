# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2019: la escala del Decimal no altera el payload firmado."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Item, SalesInvoice, SalesInvoiceItem, UOM, database
from cacao_accounting.printing.validation import ValidationService, _json_value


@pytest.mark.parametrize(
    ("escala_corta", "escala_larga"),
    [
        ("125.50", "125.5000"),
        ("0.10", "0.100000"),
        ("1000", "1000.00"),
        ("7.1234", "7.12340000"),
    ],
)
def test_la_misma_cantidad_produce_el_mismo_texto(escala_corta: str, escala_larga: str):
    """Releer de Numeric(20,4) no cambia el valor canónico."""
    assert _json_value(Decimal(escala_corta)) == _json_value(Decimal(escala_larga))


@pytest.mark.parametrize("cero", ["0", "0.0", "0.0000", "-0.00"])
def test_cero_tiene_una_sola_forma(cero: str):
    """Todas las representaciones de cero colapsan al mismo token."""
    assert _json_value(Decimal(cero)) == "0"


@pytest.mark.database
@pytest.mark.parametrize(
    ("currency_decimals", "amount"),
    [(0, "125"), (2, "125.50"), (3, "125.500"), (4, "125.5000")],
)
def test_token_sigue_valido_tras_recargar_factura_y_detecta_cambio_real(tmp_path, currency_decimals: int, amount: str):
    """La persistencia/recarga conserva el hash y una variación mínima lo invalida."""
    configured_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    database_uri = (
        f"sqlite:///{tmp_path / 'public-validation.sqlite'}" if configured_uri.startswith("sqlite") else configured_uri
    )
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "SECRET_KEY": "decimal-canonicalization-test",
        }
    )
    suffix = uuid4().hex[:7].upper()
    currency_code = f"C{suffix}"
    company_code = f"C{suffix}"
    item_code = f"I{suffix}"
    uom_code = f"U{suffix}"
    invoice_id = None
    public_token = None
    initial_amount = Decimal(amount)
    decimal_step = Decimal(1).scaleb(-currency_decimals)

    try:
        with application.app_context():
            database.create_all()
            currency = Currency(
                code=currency_code,
                name=f"Moneda de prueba {suffix}",
                decimals=currency_decimals,
                active=True,
            )
            entity = Entity(
                code=company_code,
                name=f"Empresa {suffix}",
                company_name=f"Empresa canónica {suffix}",
                tax_id=f"T{suffix}",
                currency=currency_code,
                enabled=True,
                status="activo",
            )
            uom = UOM(code=uom_code, name=f"Unidad {suffix}")
            item = Item(
                code=item_code,
                name=f"Artículo {suffix}",
                item_type="goods",
                is_stock_item=False,
                default_uom=uom_code,
            )
            database.session.add_all([currency, entity, uom])
            database.session.flush()
            database.session.add(item)
            database.session.flush()
            invoice = SalesInvoice(
                company=company_code,
                document_no=f"CAN-{suffix}",
                document_type="sales_invoice",
                posting_date=date(2026, 5, 15),
                transaction_currency=currency_code,
                base_currency=currency_code,
                exchange_rate=Decimal("1"),
                docstatus=1,
                grand_total=initial_amount,
            )
            database.session.add(invoice)
            database.session.flush()
            invoice_id = str(invoice.id)
            database.session.add(
                SalesInvoiceItem(
                    sales_invoice_id=invoice_id,
                    item_code=item_code,
                    item_name=item.name,
                    qty=Decimal("1"),
                    qty_in_base_uom=Decimal("1"),
                    uom=uom_code,
                    rate=initial_amount,
                    amount=initial_amount,
                )
            )
            database.session.commit()

            service = ValidationService()
            invoice = database.session.get(SalesInvoice, invoice_id)
            assert invoice is not None
            validation = service.update_validation_from_document(invoice)
            assert validation is not None
            database.session.commit()
            public_token = validation.public_token

            database.session.remove()
            reloaded_invoice = database.session.get(SalesInvoice, invoice_id)
            assert reloaded_invoice is not None
            assert Decimal(str(reloaded_invoice.grand_total)) == initial_amount
            assert service.validate_token(public_token)["status"] == "valid"

            reloaded_invoice.grand_total = initial_amount + decimal_step
            database.session.commit()
            database.session.remove()
            assert service.validate_token(public_token)["status"] == "invalid"
    finally:
        with application.app_context():
            from cacao_accounting.printing.models import PublicDocumentValidation

            database.session.rollback()
            if public_token:
                validations = database.session.execute(
                    database.select(PublicDocumentValidation).filter_by(public_token=public_token)
                ).scalars()
                for validation in validations:
                    database.session.delete(validation)
            if invoice_id is not None:
                lines = database.session.execute(
                    database.select(SalesInvoiceItem).filter_by(sales_invoice_id=invoice_id)
                ).scalars()
                for line in lines:
                    database.session.delete(line)
                invoice = database.session.get(SalesInvoice, invoice_id)
                if invoice:
                    database.session.delete(invoice)
            item = database.session.get(Item, item_code)
            if item:
                database.session.delete(item)
            uom = database.session.get(UOM, uom_code)
            if uom:
                database.session.delete(uom)
            entity = database.session.get(Entity, company_code)
            if entity:
                database.session.delete(entity)
            currency = database.session.get(Currency, currency_code)
            if currency:
                database.session.delete(currency)
            database.session.commit()
            database.session.remove()
            database.engine.dispose()
