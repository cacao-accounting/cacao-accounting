# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1751: el evento de creación del costo de importación se persiste."""

from datetime import date
from urllib.parse import urlparse

from cacao_accounting.database import AccountingPeriod, AuditTrail, ImportLandedCost, PurchaseInvoice, database


def test_create_import_landed_cost_persists_creation_event(app, client, reference_users):
    """El evento de creación queda persistido junto con el documento (#1751)."""
    with app.app_context():
        invoice = PurchaseInvoice(
            company="cacao",
            document_type="purchase_invoice",
            document_no="PI-LC-1751",
            posting_date=date(2026, 10, 31),
            docstatus=1,
        )
        period = AccountingPeriod(
            entity="cacao",
            name="2026-10",
            enabled=True,
            is_closed=False,
            start=date(2026, 10, 1),
            end=date(2026, 10, 31),
        )
        database.session.add_all([invoice, period])
        database.session.commit()
        invoice_id = invoice.id

    with client.session_transaction() as session:
        session["_user_id"] = str(reference_users["admin"].id)
        session["_fresh"] = True

    response = client.post(
        "/buying/import-landed-cost/new",
        data={"company": "cacao", "posting_date": "2026-10-31", "from_invoice": invoice_id},
    )

    assert response.status_code == 302
    landed_cost_id = urlparse(response.headers["Location"]).path.rstrip("/").rsplit("/", 1)[-1]

    with app.app_context():
        landed_cost = database.session.get(ImportLandedCost, landed_cost_id)
        assert landed_cost is not None
        events = (
            database.session.execute(
                database.select(AuditTrail).where(
                    AuditTrail.document_type == "import_landed_cost",
                    AuditTrail.document_id == landed_cost_id,
                    AuditTrail.action == "created",
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1
