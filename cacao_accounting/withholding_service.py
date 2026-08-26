"""Servicios de emisión y consulta de certificados de retención."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from cacao_accounting.database import Party, PaymentEntry, WithholdingCertificate, database


def _decimal(value: Any) -> Decimal:
    """Convert a monetary value to Decimal without binary floating point."""
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def create_withholding_certificate(payment: PaymentEntry, settlement: Any) -> WithholdingCertificate | None:
    """Persist one certificate for a posted supplier payment with withholding."""
    if (payment.payment_type or "").lower() != "pay" or (payment.party_type or "supplier").lower() != "supplier":
        return None
    lines = [line for line in getattr(settlement, "settlement_lines", []) if line.type == "withholding" and line.amount > 0]
    if not lines:
        return None
    existing = database.session.execute(select(WithholdingCertificate).filter_by(payment_id=payment.id)).scalar_one_or_none()
    if existing is not None:
        return existing
    supplier = database.session.get(Party, payment.party_id)
    if supplier is None:
        raise ValueError("No existe el proveedor del certificado de retención.")
    details = [
        {
            "concept": line.concept,
            "base_amount": str(line.base_amount),
            "rate": str(line.rate),
            "amount": str(line.amount),
            "account_id": line.account_id,
        }
        for line in lines
    ]
    payment_no = payment.document_no or payment.id
    certificate = WithholdingCertificate(
        company=payment.company,
        payment_id=payment.id,
        supplier_id=payment.party_id,
        supplier_name=supplier.name,
        certificate_no=f"RET-{payment_no}",
        posting_date=payment.posting_date,
        document_date=payment.document_date or payment.posting_date,
        currency=payment.currency or payment.transaction_currency,
        gross_amount=_decimal(getattr(settlement, "gross_settlement_amount", 0)),
        withheld_amount=_decimal(getattr(settlement, "withholding_amount", 0)),
        cash_amount=_decimal(getattr(settlement, "cash_amount", 0)),
        lines_json=json.dumps(details, ensure_ascii=False),
        status="issued",
        docstatus=1,
    )
    database.session.add(certificate)
    database.session.flush()
    from cacao_accounting.printing.validation import ValidationService

    ValidationService().create_or_update_validation(
        "withholding_certificate",
        certificate.id,
        {
            "company_code": certificate.company,
            "document_type": "withholding_certificate",
            "document_id": certificate.id,
            "document_number": certificate.certificate_no,
            "document_date": certificate.posting_date,
            "currency": certificate.currency,
            "grand_total": certificate.withheld_amount,
            "status": "issued",
            "party_tax_id": supplier.tax_id,
            "line_count": len(lines),
        },
    )
    return certificate


def cancel_withholding_certificate(payment_id: str) -> None:
    """Mark the certificate of a cancelled payment as cancelled."""
    certificate = database.session.execute(
        select(WithholdingCertificate).filter_by(payment_id=payment_id)
    ).scalar_one_or_none()
    if certificate is not None:
        certificate.status = "cancelled"
        certificate.docstatus = 2


def withholding_certificate_lines(certificate: WithholdingCertificate) -> list[dict[str, Any]]:
    """Decode the immutable fiscal lines stored on a certificate."""
    try:
        payload = json.loads(certificate.lines_json or "[]")
    except (TypeError, ValueError):
        return []
    return payload if isinstance(payload, list) else []
