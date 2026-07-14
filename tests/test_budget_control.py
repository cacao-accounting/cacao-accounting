# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Reyes

import pytest
from decimal import Decimal
from cacao_accounting.runtime_mode import is_desktop_mode

pytestmark = pytest.mark.skipif(is_desktop_mode(), reason="Gestión de presupuesto no disponible en modo DESKTOP")
from cacao_accounting import create_app
from cacao_accounting.contabilidad.budget_service import BudgetService
from cacao_accounting.database import (
    GLEntry,
    database,
    User,
    Entity,
    Book,
    FiscalYear,
    Accounts,
    CostCenter,
    AccountingPeriod,
    PurchaseOrder,
    PurchaseOrderItem,
    AuditTrail,
    Party,
    CompanyParty,
)
from cacao_accounting.database.helpers import inicia_base_de_datos
from cacao_accounting.setup.repository import set_setup_value


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test_secret_key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        inicia_base_de_datos(app, user="cacao", passwd="cacao", with_examples=False)
        from cacao_accounting.datos.dev import master_data

        if not database.session.execute(database.select(Entity).filter_by(code="cacao")).first():
            master_data()
        yield app


def test_budget_control_validate_transaction(app_ctx):
    service = BudgetService()
    admin_user = database.session.query(User).filter_by(user="admin").first()

    fy = database.session.query(FiscalYear).filter_by(entity="cacao").first()
    book = database.session.query(Book).filter_by(entity="cacao", is_primary=True).first()
    if not book:
        book = database.session.query(Book).filter_by(entity="cacao").first()

    # Create approved budget
    budget = service.create_budget(
        {
            "company": "cacao",
            "ledger_id": book.id,
            "fiscal_year_id": fy.id,
            "budget_code": "CTRL-2026",
            "name": "Budget Control test",
            "currency_id": "NIO",
        },
        str(admin_user.id),
    )

    acc = database.session.query(Accounts).filter_by(entity="cacao", group=False).first()
    cc = database.session.query(CostCenter).filter_by(entity="cacao").first()
    per = database.session.query(AccountingPeriod).filter_by(fiscal_year_id=fy.id).first()

    service.add_budget_line(
        budget.id,
        {
            "account_id": acc.id,
            "cost_center_id": cc.id,
            "period_id": per.id,
            "amount": 1000,
        },
        str(admin_user.id),
    )

    service.approve_budget(budget.id, str(admin_user.id))

    # GLEntry actual commit of 300
    gl_entry = GLEntry(
        company="cacao",
        ledger_id=book.id,
        account_id=acc.id,
        account_code=acc.code,
        cost_center_code=cc.code,
        accounting_period_id=per.id,
        posting_date=per.start,
        debit=Decimal("300"),
        credit=Decimal("0"),
        is_cancelled=False,
        is_fiscal_year_closing=False,
        voucher_type="journal_entry",
        voucher_id="JRN-TEST",
        document_no="cacao-JOU-TEST",
    )
    database.session.add(gl_entry)
    database.session.commit()

    # Validation scenario
    # Requested 500. Total budget: 1000. Committed: 300. Available: 700. Requested: 500. Exceeded: False
    res = service.validate_transaction(
        company="cacao",
        date_val=per.start,
        account_id=acc.id,
        cost_center_id=cc.id,
        amount=Decimal("500"),
        document_id="DOC1",
        document_type="purchase_order",
    )

    assert res["exceeded"] is False
    assert res["budget"] == Decimal("1000")
    assert res["committed"] == Decimal("300")
    assert res["available"] == Decimal("700")
    assert res["requested"] == Decimal("500")
    assert res["excess"] == Decimal("0")

    # Requested 800. Exceeded: True, excess: 100
    res_exceeded = service.validate_transaction(
        company="cacao",
        date_val=per.start,
        account_id=acc.id,
        cost_center_id=cc.id,
        amount=Decimal("800"),
        document_id="DOC2",
        document_type="purchase_order",
    )

    assert res_exceeded["exceeded"] is True
    assert res_exceeded["excess"] == Decimal("100")


def test_budget_control_config_views(app_ctx):
    admin_user = database.session.query(User).filter_by(user="admin").first()

    with app_ctx.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = admin_user.id
            session["_fresh"] = True

        # GET config page
        response = client.get("/settings/budget-control")
        assert response.status_code == 200
        assert b"Configuraci\xc3\xb3n de Control Presupuestario" in response.data

        # POST config to enable block
        response_post = client.post(
            "/settings/budget-control", data={"company": "cacao", "enabled": "on", "action_on_exceeded": "block"}
        )
        assert response_post.status_code == 302

        # GET again to verify
        response_get = client.get("/settings/budget-control")
        assert response_get.status_code == 200
        assert b"block" in response_get.data


def test_budget_control_scenarios_po_pr(app_ctx):
    service = BudgetService()
    admin_user = database.session.query(User).filter_by(user="admin").first()
    fy = database.session.query(FiscalYear).filter_by(entity="cacao").first()
    book = database.session.query(Book).filter_by(entity="cacao", is_primary=True).first()
    if not book:
        book = database.session.query(Book).filter_by(entity="cacao").first()

    # Create approved budget with 1000 NIO
    budget = service.create_budget(
        {
            "company": "cacao",
            "ledger_id": book.id,
            "fiscal_year_id": fy.id,
            "budget_code": "SCENARIOS-2026",
            "name": "Budget Scenarios",
            "currency_id": "NIO",
        },
        str(admin_user.id),
    )

    acc = database.session.query(Accounts).filter_by(entity="cacao", group=False).first()
    cc = database.session.query(CostCenter).filter_by(entity="cacao").first()
    per = database.session.query(AccountingPeriod).filter_by(fiscal_year_id=fy.id).first()

    service.add_budget_line(
        budget.id,
        {
            "account_id": acc.id,
            "cost_center_id": cc.id,
            "period_id": per.id,
            "amount": 1000,
        },
        str(admin_user.id),
    )

    service.approve_budget(budget.id, str(admin_user.id))

    # Resolve items, make sure we have a mapping to the budgeted account/cost center
    from cacao_accounting.database import Item, ItemAccount

    item = database.session.query(Item).filter_by(is_active=True).first()
    # Map item to budgeted account and cost center
    item_acc = ItemAccount(item_code=item.code, company="cacao", expense_account_id=acc.id, cost_center_code=cc.code)
    database.session.add(item_acc)

    # Supplier
    supplier = database.session.query(Party).filter_by(is_supplier=True).first()
    # CompanyParty
    cp = database.session.query(CompanyParty).filter_by(company="cacao", party_id=supplier.id).first()
    if cp:
        cp.allow_purchase_invoice_without_order = True
        cp.allow_purchase_invoice_without_receipt = True
    else:
        cp = CompanyParty(
            company="cacao",
            party_id=supplier.id,
            allow_purchase_invoice_without_order=True,
            allow_purchase_invoice_without_receipt=True,
        )
        database.session.add(cp)
    database.session.commit()

    # Direct testing check_budget_control
    from cacao_accounting.compras import check_budget_control

    # Test Case 1: Budget Control is OFF
    set_setup_value("budget_control_enabled_cacao", "0")
    database.session.commit()

    po = PurchaseOrder(
        company="cacao",
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        posting_date=per.start,
        docstatus=0,
        grand_total=Decimal("1500"),
    )
    database.session.add(po)
    database.session.flush()

    po_item = PurchaseOrderItem(
        purchase_order_id=po.id, item_code=item.code, qty=Decimal("1"), rate=Decimal("1500"), amount=Decimal("1500")
    )
    database.session.add(po_item)
    database.session.commit()

    # Call direct check_budget_control - should return None (no exception)
    with app_ctx.test_request_context():
        check_budget_control(
            company=po.company,
            posting_date=po.posting_date,
            supplier_id=po.supplier_id,
            document_id=po.id,
            document_type="purchase_order",
            items=[po_item],
        )

    # Test Case 2: Budget Control is ON, Mode = do_nothing
    set_setup_value("budget_control_enabled_cacao", "1")
    set_setup_value("budget_control_action_cacao", "do_nothing")
    database.session.commit()

    with app_ctx.test_request_context():
        check_budget_control(
            company=po.company,
            posting_date=po.posting_date,
            supplier_id=po.supplier_id,
            document_id=po.id,
            document_type="purchase_order",
            items=[po_item],
        )
    # Check Audit Trail log
    audit = (
        database.session.query(AuditTrail)
        .filter_by(document_type="purchase_order", document_id=po.id, action="budget_exceeded")
        .first()
    )
    assert audit is not None
    assert "do_nothing" in audit.comment

    # Test Case 3: Budget Control is ON, Mode = notify
    set_setup_value("budget_control_action_cacao", "notify")
    database.session.commit()

    # Call direct check_budget_control - should not raise exception
    with app_ctx.test_request_context():
        check_budget_control(
            company=po.company,
            posting_date=po.posting_date,
            supplier_id=po.supplier_id,
            document_id=po.id,
            document_type="purchase_order",
            items=[po_item],
        )

    # Test Case 4: Budget Control is ON, Mode = block
    set_setup_value("budget_control_action_cacao", "block")
    database.session.commit()

    # Call direct check_budget_control - should raise ValueError
    with app_ctx.test_request_context():
        with pytest.raises(ValueError, match="No es posible aprobar el documento."):
            check_budget_control(
                company=po.company,
                posting_date=po.posting_date,
                supplier_id=po.supplier_id,
                document_id=po.id,
                document_type="purchase_order",
                items=[po_item],
            )

    # Verify that the audit trail entry was actually committed/persisted
    audit4 = (
        database.session.query(AuditTrail)
        .filter_by(document_type="purchase_order", document_id=po.id, action="budget_exceeded")
        .filter(AuditTrail.comment.contains("block"))
        .first()
    )
    assert audit4 is not None
