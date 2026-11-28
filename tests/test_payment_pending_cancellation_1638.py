# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1638: el detalle de pago no ofrece anular si ya hay una anulación pendiente."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import ApprovalRequest, Party, PaymentEntry, User, database

FECHA = date(2026, 5, 20)


def _pago(app) -> tuple[str, str]:
    """Crea un pago aprobado de la compañía sembrada."""
    with app.app_context():
        sufijo = uuid4().hex[:6].upper()
        proveedor = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        pago = PaymentEntry(
            company="cacao",
            document_no=f"PAY-1638-{sufijo}",
            payment_type="pay",
            party_type="supplier",
            party_id=proveedor.id,
            party_name=proveedor.name,
            posting_date=FECHA,
            paid_amount=Decimal("100"),
            received_amount=Decimal("100"),
            currency="NIO",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            docstatus=1,
        )
        database.session.add(pago)
        database.session.commit()
        return pago.id, sufijo


def _solicitar_anulacion(app, payment_id: str) -> None:
    """Registra la solicitud de anulación pendiente del pago."""
    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        database.session.add(
            ApprovalRequest(
                document_type="cancel_payment_entry",
                document_id=payment_id,
                company_id="cacao",
                requested_by=str(admin.id),
                current_level=1,
                required_level=1,
                status="Pending Cancellation",
                created_at=datetime.now(timezone.utc),
                cancellation_reason="Anulación solicitada",
            )
        )
        database.session.commit()


def test_el_pago_con_anulacion_pendiente_no_ofrece_anular(app, entorno_contable, authenticated_client):
    """El badge refleja la solicitud y no se repite el enlace de anulación."""
    del entorno_contable
    payment_id, _ = _pago(app)
    _solicitar_anulacion(app, payment_id)

    respuesta = authenticated_client("admin").get(f"/cash_management/payment/{payment_id}")

    cuerpo = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert "Anulación Pendiente" in cuerpo
    assert f"/cash_management/payment/{payment_id}/cancel" not in cuerpo


def test_el_pago_sin_solicitud_conserva_la_accion_de_anular(app, entorno_contable, authenticated_client):
    """Sin solicitud pendiente el detalle mantiene el botón Anular."""
    del entorno_contable
    payment_id, _ = _pago(app)

    respuesta = authenticated_client("admin").get(f"/cash_management/payment/{payment_id}")

    cuerpo = respuesta.get_data(as_text=True)
    assert respuesta.status_code == 200
    assert f"/cash_management/payment/{payment_id}/cancel" in cuerpo
