# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1751: el evento de creación del costo de importación se persiste."""

from datetime import date
from urllib.parse import urlparse

import pytest

from cacao_accounting.database import AccountingPeriod, AuditTrail, ImportLandedCost, PurchaseInvoice, User, database


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


def test_fallo_al_persistir_auditoria_revierte_el_documento(entorno_contable_aislado, monkeypatch):
    """Un fallo de auditoría no deja costo persistido desde una sesión nueva (#1751)."""
    import importlib

    escenario = entorno_contable_aislado
    app = escenario.app
    with app.app_context():
        invoice = PurchaseInvoice(
            company="cacao",
            document_type="purchase_invoice",
            document_no="PI-LC-1751-AUDIT",
            posting_date=date(2026, 5, 20),
            docstatus=1,
        )
        database.session.add(invoice)
        database.session.commit()
        invoice_id = invoice.id
        admin_id = database.session.execute(database.select(User.id).filter_by(user="admin")).scalar_one()

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(admin_id)
        session["_fresh"] = True

    def fail_audit(_registro):
        raise RuntimeError("auditoría no disponible")

    services_module = importlib.import_module("cacao_accounting.compras.services")
    monkeypatch.setattr(services_module, "log_create", fail_audit)

    with pytest.raises(RuntimeError, match="auditoría no disponible"):
        client.post(
            "/buying/import-landed-cost/new",
            data={"company": "cacao", "posting_date": "2026-05-20", "from_invoice": invoice_id},
        )

    # La SQLite en memoria comparte una única conexión (StaticPool) y el writer
    # abre la transacción con BEGIN IMMEDIATE; se descarta la transacción cruda
    # antes de comprobar que nada quedó confirmado.
    database.session.remove()
    with database.engine.connect() as conn:
        try:
            conn.exec_driver_sql("ROLLBACK")
        except Exception:
            pass

    with app.app_context():
        assert (
            database.session.execute(database.select(ImportLandedCost).filter_by(purchase_invoice_id=invoice_id))
            .scalars()
            .all()
            == []
        )
        assert (
            database.session.execute(database.select(AuditTrail).filter_by(document_type="import_landed_cost")).scalars().all()
            == []
        )
