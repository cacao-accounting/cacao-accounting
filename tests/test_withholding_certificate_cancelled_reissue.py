# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresiones para la emisión idempotente de certificados de retención."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import inspect, select

from cacao_accounting.database import Party, PaymentEntry, WithholdingCertificate, database
from cacao_accounting.withholding_service import create_withholding_certificate


@pytest.mark.parametrize("status,docstatus", [("cancelled", 2), ("issued", 2), ("cancelled", 1)])
def test_no_reemite_ni_devuelve_certificado_cancelado(entorno_contable_aislado, status: str, docstatus: int) -> None:
    """Un certificado no vigente bloquea la reemisión sin alterar su evidencia."""
    with entorno_contable_aislado.app.app_context():
        supplier_id = inspect(entorno_contable_aislado.supplier).identity[0]
        proveedor = database.session.get(Party, supplier_id)
        payment = PaymentEntry(
            company="cacao",
            posting_date=date(2026, 11, 10),
            payment_type="pay",
            party_type="supplier",
            party_id=proveedor.id,
            party_name=proveedor.name,
            currency="NIO",
            document_no="PAY-REISSUE",
            docstatus=1,
        )
        database.session.add(payment)
        database.session.flush()
        certificate = WithholdingCertificate(
            company=payment.company,
            payment_id=payment.id,
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
            certificate_no="RET-PAY-REISSUE",
            posting_date=payment.posting_date,
            document_date=payment.posting_date,
            currency="NIO",
            gross_amount=Decimal("100.00"),
            withheld_amount=Decimal("10.00"),
            cash_amount=Decimal("90.00"),
            lines_json='[{"amount":"10.00"}]',
            status=status,
            docstatus=docstatus,
        )
        database.session.add(certificate)
        database.session.flush()
        settlement = SimpleNamespace(
            settlement_lines=[
                SimpleNamespace(
                    type="withholding",
                    amount=Decimal("10.00"),
                    concept="Retención",
                    base_amount=Decimal("100.00"),
                    rate=Decimal("10"),
                    account_id="withholding-account",
                )
            ],
            gross_settlement_amount=Decimal("100.00"),
            withholding_amount=Decimal("10.00"),
            cash_amount=Decimal("90.00"),
        )

        with pytest.raises(ValueError, match="no puede reemitirse"):
            create_withholding_certificate(payment, settlement)

        assert certificate.status == status
        assert certificate.docstatus == docstatus
        assert certificate.lines_json == '[{"amount":"10.00"}]'
        assert database.session.execute(select(WithholdingCertificate).filter_by(payment_id=payment.id)).scalars().all() == [
            certificate
        ]
        database.session.rollback()


def test_repetir_emision_devuelve_certificado_vigente(entorno_contable_aislado) -> None:
    """La repetición de una emisión vigente mantiene el comportamiento idempotente."""
    with entorno_contable_aislado.app.app_context():
        supplier_id = inspect(entorno_contable_aislado.supplier).identity[0]
        proveedor = database.session.get(Party, supplier_id)
        payment = PaymentEntry(
            company="cacao",
            posting_date=date(2026, 11, 10),
            payment_type="pay",
            party_type="supplier",
            party_id=proveedor.id,
            party_name=proveedor.name,
            currency="NIO",
            document_no="PAY-IDEMPOTENT",
            docstatus=1,
        )
        database.session.add(payment)
        database.session.flush()
        certificate = WithholdingCertificate(
            company=payment.company,
            payment_id=payment.id,
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
            certificate_no="RET-PAY-IDEMPOTENT",
            posting_date=payment.posting_date,
            document_date=payment.posting_date,
            currency="NIO",
            gross_amount=Decimal("100.00"),
            withheld_amount=Decimal("10.00"),
            cash_amount=Decimal("90.00"),
            lines_json="[]",
            status="issued",
            docstatus=1,
        )
        database.session.add(certificate)
        database.session.flush()
        settlement = SimpleNamespace(settlement_lines=[SimpleNamespace(type="withholding", amount=Decimal("10.00"))])

        assert create_withholding_certificate(payment, settlement) is certificate
        assert database.session.execute(select(WithholdingCertificate).filter_by(payment_id=payment.id)).scalars().all() == [
            certificate
        ]
        database.session.rollback()
