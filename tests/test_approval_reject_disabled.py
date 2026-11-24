# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2008: el rechazo con solicitud pendiente funciona con el motor deshabilitado."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import (
    ApprovalAction,
    ApprovalRequest,
    CacaoConfig,
    GLEntry,
    SalesInvoice,
    User,
    database,
)


def _deshabilitar_motor() -> tuple[str | None, bool]:
    """Deshabilita el motor y devuelve el valor y existencia previos."""
    clave = "approval_engine_enabled_cacao"
    registro = database.session.execute(database.select(CacaoConfig).filter_by(key=clave)).scalar_one_or_none()
    anterior = None if registro is None else registro.value
    creado = registro is None
    if registro is None:
        database.session.add(CacaoConfig(key=clave, value="false"))
    else:
        registro.value = "false"
    database.session.commit()
    return anterior, creado


def test_rechazo_http_con_solicitud_pendiente_ignora_motor_deshabilitado(app, entorno_contable, authenticated_client):
    """Con una solicitud pendiente el rechazo aplica la transición y registra la acción."""
    del entorno_contable
    sufijo = uuid4().hex[:8]
    anterior = None
    creado = True
    with app.app_context():
        anterior, creado = _deshabilitar_motor()
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        factura = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=0,
            document_no=f"REJ-{sufijo}",
            customer_name="Cliente rechazo",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("10"),
            total=Decimal("10"),
            outstanding_amount=Decimal("10"),
        )
        database.session.add(factura)
        database.session.flush()
        solicitud = ApprovalRequest(
            document_type="sales_invoice",
            document_id=factura.id,
            company_id="cacao",
            requested_by=admin.id,
            current_level=1,
            required_level=1,
            status="Pending Approval",
        )
        database.session.add(solicitud)
        database.session.commit()
        factura_id, solicitud_id = factura.id, solicitud.id

    try:
        response = authenticated_client("admin").post(
            "/me/pending-approvals",
            data={"request_id": solicitud_id, "action": "reject", "comments": "Rechazo con motor off"},
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "rechazado" in response.get_data(as_text=True).lower()
        with app.app_context():
            persistida = database.session.get(ApprovalRequest, solicitud_id)
            assert persistida.status == "Rejected"
            acciones = (
                database.session.execute(database.select(ApprovalAction).filter_by(approval_request_id=solicitud_id))
                .scalars()
                .all()
            )
            assert len(acciones) == 1
            assert acciones[0].action == "reject"
            assert acciones[0].comments == "Rechazo con motor off"
            factura_tras = database.session.get(SalesInvoice, factura_id)
            assert factura_tras is not None
            assert factura_tras.docstatus == 0
            assert factura_tras.grand_total == Decimal("10")
            assert database.session.execute(database.select(GLEntry).filter_by(voucher_id=factura_id)).scalars().all() == []
    finally:
        with app.app_context():
            database.session.execute(database.delete(ApprovalAction).where(ApprovalAction.approval_request_id == solicitud_id))
            database.session.execute(database.delete(ApprovalRequest).where(ApprovalRequest.id == solicitud_id))
            factura = database.session.get(SalesInvoice, factura_id)
            if factura is not None:
                database.session.delete(factura)
            registro = database.session.execute(
                database.select(CacaoConfig).filter_by(key="approval_engine_enabled_cacao")
            ).scalar_one_or_none()
            if registro is not None:
                if creado:
                    database.session.delete(registro)
                else:
                    registro.value = anterior
            database.session.commit()
