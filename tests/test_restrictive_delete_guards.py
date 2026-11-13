# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Master records with persisted restrictive references cannot be deleted."""

from __future__ import annotations

import os
from datetime import date
from uuid import uuid4

import pytest


from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    BalanceConfirmation,
    Batch,
    Currency,
    Entity,
    Item,
    Party,
    PaymentEntry,
    PaymentReference,
    RecurringJournalItem,
    RecurringJournalTemplate,
    UOM,
    Warehouse,
    WarehouseCompanyAccount,
    WithholdingCertificate,
    database,
)
from cacao_accounting.exceptions import IntegrityError as CacaoIntegrityError

pytestmark = pytest.mark.database


@pytest.fixture
def restrictive_delete_scenario(tmp_path):
    """Create real master and evidence rows in an isolated database."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'restrictive-delete.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")

    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        database.create_all()
        suffix = uuid4().hex[:7].upper()
        currency = Currency(code=f"X{suffix}", name="Moneda integridad", decimals=2, active=True, default=False)
        company = Entity(
            code=f"C{suffix}",
            name=f"Empresa integridad {suffix}",
            company_name=f"Empresa integridad {suffix} SA",
            tax_id=f"T{suffix}",
            currency=currency.code,
            enabled=True,
            status="default",
        )
        uom = UOM(code=f"U{suffix}", name="Unidad integridad", is_active=True)
        database.session.add_all([currency, company, uom])
        database.session.flush()

        item = Item(
            code=f"I{suffix}",
            name="Artículo con lote",
            item_type="goods",
            is_stock_item=True,
            default_uom=uom.code,
        )
        warehouse = Warehouse(code=f"W{suffix}", name="Bodega con cuenta", company=company.code)
        balance_party = Party(code=f"PB{suffix}", name="Proveedor con confirmación", is_supplier=True)
        certificate_party = Party(code=f"PC{suffix}", name="Proveedor con certificado", is_supplier=True)
        payment_party = Party(code=f"PR{suffix}", name="Proveedor con aplicación", is_supplier=True)
        template_party = Party(code=f"PT{suffix}", name="Proveedor en plantilla recurrente", is_supplier=True)
        template = RecurringJournalTemplate(
            code=f"RJT-{suffix}",
            company=company.code,
            name="Plantilla de pago recurrente",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            currency=currency.code,
        )
        database.session.add_all([item, warehouse, balance_party, certificate_party, payment_party, template_party, template])
        database.session.flush()

        batch = Batch(item_code=item.code, batch_no=f"LOT-{suffix}")
        warehouse_account = WarehouseCompanyAccount(warehouse_code=warehouse.code, company=company.code)
        confirmation = BalanceConfirmation(
            company=company.code,
            party_type="supplier",
            party_id=balance_party.id,
            cutoff_date=date(2026, 11, 1),
        )
        payment = PaymentEntry(payment_type="pay", company=company.code)
        database.session.add_all([batch, warehouse_account, confirmation, payment])
        database.session.flush()
        payment_reference = PaymentReference(
            payment_id=payment.id,
            reference_type="purchase_invoice",
            reference_id=f"INV-{suffix}",
            party_type="supplier",
            party_id=payment_party.id,
            company=company.code,
            allocated_amount=1,
        )
        recurring_item = RecurringJournalItem(
            template_id=template.id,
            account_code="6000",
            debit=1,
            credit=0,
            party_type="supplier",
            party_id=template_party.id,
        )
        certificate = WithholdingCertificate(
            payment_id=payment.id,
            supplier_id=certificate_party.id,
            supplier_name=certificate_party.name,
            certificate_no=f"CERT-{suffix}",
            lines_json="[]",
        )
        database.session.add_all([payment_reference, recurring_item, certificate])
        database.session.commit()

        scenario = {
            "app": app,
            "items": (item.id, batch.id),
            "uom_code": uom.code,
            "warehouses": (warehouse.id, warehouse_account.id),
            "parties": (balance_party.id, confirmation.id),
            "certified_parties": (certificate_party.id, certificate.id),
            "payment_party": (payment_party.id, payment_reference.id),
            "template_party": (template_party.id, recurring_item.id),
        }

    yield scenario

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _assert_restricted_delete_is_rejected(model, record_id: str, message: str) -> None:
    """Keep a master and its evidence intact when its ORM delete is attempted."""
    record = database.session.get(model, record_id)
    assert record is not None
    with pytest.raises(CacaoIntegrityError, match=message):
        database.session.delete(record)
        database.session.flush()
    database.session.rollback()
    assert database.session.get(model, record_id) is not None


def test_declared_restrict_references_block_master_deletion(restrictive_delete_scenario):
    """Preserve stock, warehouse configuration, and AP confirmation evidence."""
    app = restrictive_delete_scenario["app"]
    with app.app_context():
        item_id, batch_id = restrictive_delete_scenario["items"]
        _assert_restricted_delete_is_rejected(Item, item_id, "artículo cuenta con transacciones")
        batch = database.session.get(Batch, batch_id)
        assert batch is not None and database.session.get(Item, item_id) is not None
        assert batch.item_code == database.session.get(Item, item_id).code

        warehouse_id, account_id = restrictive_delete_scenario["warehouses"]
        _assert_restricted_delete_is_rejected(Warehouse, warehouse_id, "bodega cuenta con transacciones")
        warehouse_account = database.session.get(WarehouseCompanyAccount, account_id)
        warehouse = database.session.get(Warehouse, warehouse_id)
        assert warehouse_account is not None and warehouse is not None
        assert warehouse_account.warehouse_code == warehouse.code

        party_id, confirmation_id = restrictive_delete_scenario["parties"]
        _assert_restricted_delete_is_rejected(Party, party_id, "cliente/proveedor cuenta con transacciones")
        confirmation = database.session.get(BalanceConfirmation, confirmation_id)
        party = database.session.get(Party, party_id)
        assert confirmation is not None and party is not None
        assert confirmation.party_id == party.id

        certified_party_id, certificate_id = restrictive_delete_scenario["certified_parties"]
        _assert_restricted_delete_is_rejected(Party, certified_party_id, "cliente/proveedor cuenta con transacciones")
        certificate = database.session.get(WithholdingCertificate, certificate_id)
        certified_party = database.session.get(Party, certified_party_id)
        assert certificate is not None and certified_party is not None
        assert certificate.supplier_id == certified_party.id

        payment_party_id, payment_reference_id = restrictive_delete_scenario["payment_party"]
        _assert_restricted_delete_is_rejected(Party, payment_party_id, "cliente/proveedor cuenta con transacciones")
        payment_reference = database.session.get(PaymentReference, payment_reference_id)
        payment_party = database.session.get(Party, payment_party_id)
        assert payment_reference is not None and payment_party is not None
        assert payment_reference.party_id == payment_party.id

        template_party_id, recurring_item_id = restrictive_delete_scenario["template_party"]
        _assert_restricted_delete_is_rejected(Party, template_party_id, "cliente/proveedor cuenta con transacciones")
        recurring_item = database.session.get(RecurringJournalItem, recurring_item_id)
        template_party = database.session.get(Party, template_party_id)
        assert recurring_item is not None and template_party is not None
        assert recurring_item.party_id == template_party.id

        unused_item = Item(
            code=f"U{uuid4().hex[:7].upper()}",
            name="Artículo sin referencias",
            item_type="goods",
            default_uom=restrictive_delete_scenario["uom_code"],
        )
        database.session.add(unused_item)
        database.session.commit()
        unused_item_id = unused_item.id
        database.session.delete(unused_item)
        database.session.commit()
        assert database.session.get(Item, unused_item_id) is None
