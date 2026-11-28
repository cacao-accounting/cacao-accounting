# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1804: solicitudes y cotizaciones pendientes no pueden editarse."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select

from cacao_accounting.database import (
    ApprovalRequest,
    PurchaseQuotation,
    PurchaseRequest,
    SupplierQuotation,
    User,
    database,
)

FECHA = date(2026, 5, 15)
CASOS = (
    (PurchaseRequest, "purchase_request", "/buying/purchase-request/{}/edit"),
    (PurchaseQuotation, "purchase_quotation", "/buying/request-for-quotation/{}/edit"),
    (SupplierQuotation, "supplier_quotation", "/buying/supplier-quotation/{}/edit"),
)


def _cliente(app):
    """Autentica al administrador de la aplicación aislada."""
    with app.app_context():
        admin = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        admin_id = str(inspect(admin).identity[0])
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = admin_id
        session["_fresh"] = True
    return client


@pytest.mark.parametrize("model,doctype,path", CASOS)
@pytest.mark.parametrize("method", ["get", "post"])
def test_edicion_pendiente_devuelve_409_sin_mutar(entorno_contable_aislado, model, doctype, path, method):
    """GET y POST bloquean la edición antes de cambiar el documento pendiente."""
    app = entorno_contable_aislado.app
    suffix = uuid4().hex[:8]
    with app.app_context():
        admin = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        document = model(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            document_no=f"PEND-1804-{suffix}",
            remarks="Original",
        )
        database.session.add(document)
        database.session.flush()
        database.session.add(
            ApprovalRequest(
                document_type=doctype,
                document_id=document.id,
                company_id="cacao",
                requested_by=admin.id,
                current_level=1,
                required_level=1,
                status="Pending Approval",
            )
        )
        database.session.commit()
        document_id = document.id

    client = _cliente(app)
    if method == "get":
        response = client.get(path.format(document_id))
    else:
        response = client.post(
            path.format(document_id),
            data={"company": "cacao", "posting_date": FECHA.isoformat(), "remarks": "No debe persistir"},
        )

    assert response.status_code == 409
    with app.app_context():
        persisted = database.session.get(model, document_id)
        assert persisted is not None
        assert persisted.remarks == "Original"
        assert persisted.docstatus == 0
