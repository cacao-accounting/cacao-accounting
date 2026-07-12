# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Reyes

import pytest
from decimal import Decimal
from cacao_accounting.runtime_mode import is_desktop_mode

pytestmark = pytest.mark.skipif(is_desktop_mode(), reason="Gestión de presupuesto no disponible en modo DESKTOP")
from types import SimpleNamespace
from cacao_accounting import create_app
from cacao_accounting.contabilidad.budget_service import BudgetService, BudgetError
from cacao_accounting.contabilidad.budget_report_service import BudgetReportService
from cacao_accounting.database import (
    GLEntry,
    BudgetLine,
    database,
    User,
    Entity,
    Book,
    FiscalYear,
    Accounts,
    CostCenter,
    AccountingPeriod,
    Unit,
    Project,
)
from cacao_accounting.database.helpers import inicia_base_de_datos


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


def test_budget_lifecycle(app_ctx):
    service = BudgetService()
    admin_user = database.session.query(User).filter_by(user="admin").first()

    # Buscar datos del master data
    fy = database.session.query(FiscalYear).filter_by(entity="cacao").first()
    book = database.session.query(Book).filter_by(entity="cacao", is_primary=True).first()
    if not book:
        book = database.session.query(Book).filter_by(entity="cacao").first()

    data = {
        "company": "cacao",
        "ledger_id": book.id,
        "fiscal_year_id": fy.id,
        "budget_code": "TEST-2026",
        "name": "Presupuesto de Prueba",
        "currency_id": "NIO",
    }
    budget = service.create_budget(data, str(admin_user.id))
    assert budget.status == "draft"

    # 2. Agregar línea
    acc = database.session.query(Accounts).filter_by(entity="cacao", group=False).first()
    cc = database.session.query(CostCenter).filter_by(entity="cacao").first()
    per = database.session.query(AccountingPeriod).filter_by(fiscal_year_id=fy.id).first()

    line_data = {
        "account_id": acc.id,
        "cost_center_id": cc.id,
        "period_id": per.id,
        "amount": 1000,
    }
    line = service.add_budget_line(budget.id, line_data, str(admin_user.id))
    assert line.amount == Decimal("1000")

    # 3. Aprobar
    service.approve_budget(budget.id, str(admin_user.id))
    assert budget.status == "approved"

    # 4. Reporte
    report_service = BudgetReportService()
    report = report_service.get_real_vs_budget_report(
        {"company": "cacao", "budget_id": budget.id, "ledger_id": book.id, "fiscal_year_id": fy.id, "granularity": "month"}
    )
    assert len(report.rows) > 0
    assert report.totals["budget"] == Decimal("1000")


def test_duplicate_budget_code(app_ctx):
    service = BudgetService()
    admin_user = database.session.query(User).filter_by(user="admin").first()
    fy = database.session.query(FiscalYear).filter_by(entity="cacao").first()
    book = database.session.query(Book).filter_by(entity="cacao").first()

    data = {
        "company": "cacao",
        "ledger_id": book.id,
        "fiscal_year_id": fy.id,
        "budget_code": "DUP-CODE",
        "name": "P1",
        "currency_id": "NIO",
    }
    service.create_budget(data, str(admin_user.id))

    with pytest.raises(BudgetError, match="El código de presupuesto ya existe"):
        service.create_budget(data, str(admin_user.id))


def test_budget_import(app_ctx):
    from cacao_accounting.contabilidad.budget_import_service import BudgetImportService
    from cacao_accounting.database import BudgetImportLine

    service = BudgetService()
    import_service = BudgetImportService()
    admin_user = database.session.query(User).filter_by(user="admin").first()
    fy = database.session.query(FiscalYear).filter_by(entity="cacao").first()
    book = database.session.query(Book).filter_by(entity="cacao").first()
    acc = database.session.query(Accounts).filter_by(entity="cacao", group=False).all()
    cc = database.session.query(CostCenter).filter_by(entity="cacao").first()
    per = database.session.query(AccountingPeriod).filter_by(fiscal_year_id=fy.id).first()

    budget = service.create_budget(
        {
            "company": "cacao",
            "ledger_id": book.id,
            "fiscal_year_id": fy.id,
            "budget_code": "IMPORT-TEST",
            "name": "Import Test",
            "currency_id": "NIO",
        },
        str(admin_user.id),
    )

    # CSV content
    csv_content = f"Cuenta,Centro de Costo,Unidad de Negocio,Proyecto,Descripción,{per.name},Total\n"
    csv_content += f"{acc[0].code},{cc.code},,,Test Import,500,500\n"

    # 1. Validate & Stage
    batch = import_service.validate_import(budget.id, "test.csv", csv_content.encode("utf-8"), str(admin_user.id))
    assert batch.status == "validated"
    assert batch.rows_inserted == 1
    staged = database.session.query(BudgetImportLine).filter_by(import_id=batch.id).all()
    assert len(staged) == 1
    assert staged[0].row_index == 2

    # 2. Commit to live
    import_service.insert_lines(batch.id, str(admin_user.id))

    # Verify
    lines = database.session.query(BudgetLine).filter_by(budget_id=budget.id).all()
    assert len(lines) == 1
    assert lines[0].amount == Decimal("500")


def test_budget_import_route_uses_shared_template(app_ctx, monkeypatch):
    from cacao_accounting.contabilidad import presupuesto as presupuesto_module

    service = BudgetService()
    admin_user = database.session.query(User).filter_by(user="admin").first()
    fy = database.session.query(FiscalYear).filter_by(entity="cacao").first()
    book = database.session.query(Book).filter_by(entity="cacao").first()

    budget = service.create_budget(
        {
            "company": "cacao",
            "ledger_id": book.id,
            "fiscal_year_id": fy.id,
            "budget_code": "ROUTE-IMPORT-TEST",
            "name": "Route Import Test",
            "currency_id": "NIO",
        },
        str(admin_user.id),
    )

    captured: dict[str, str] = {}

    def fake_render_template(template_name: str, **context):
        captured["template"] = template_name
        captured["budget_id"] = context["budget"].id
        return template_name

    monkeypatch.setattr(presupuesto_module, "render_template", fake_render_template)
    monkeypatch.setattr(presupuesto_module, "Permisos", lambda *args, **kwargs: SimpleNamespace(importar=True))

    with app_ctx.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = admin_user.id
            session["_fresh"] = True

        response = client.get(f"/accounting/presupuestos/{budget.id}/import")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "contabilidad/presupuestos/import.html"
    assert captured["template"] == "contabilidad/presupuestos/import.html"
    assert captured["budget_id"] == budget.id


def test_budget_uniqueness_validation(app_ctx):
    service = BudgetService()
    admin_user = database.session.query(User).filter_by(user="admin").first()
    fy = database.session.query(FiscalYear).filter_by(entity="cacao").first()
    book = database.session.query(Book).filter_by(entity="cacao").first()
    acc = database.session.query(Accounts).filter_by(entity="cacao", group=False).first()
    cc = database.session.query(CostCenter).filter_by(entity="cacao").first()
    per = database.session.query(AccountingPeriod).filter_by(fiscal_year_id=fy.id).first()

    budget = service.create_budget(
        {
            "company": "cacao",
            "ledger_id": book.id,
            "fiscal_year_id": fy.id,
            "budget_code": "UNIQUE-TEST",
            "name": "Unique Test",
            "currency_id": "NIO",
        },
        str(admin_user.id),
    )

    line_data = {"account_id": acc.id, "cost_center_id": cc.id, "period_id": per.id, "amount": 100}
    service.add_budget_line(budget.id, line_data, str(admin_user.id))

    with pytest.raises(BudgetError, match="Ya existe una línea para esta combinación"):
        service.add_budget_line(budget.id, line_data, str(admin_user.id))


def test_budget_line_validation_rejects_invalid_dimensions(app_ctx):
    service = BudgetService()
    admin_user = database.session.query(User).filter_by(user="admin").first()
    fy = database.session.query(FiscalYear).filter_by(entity="cacao").first()
    book = database.session.query(Book).filter_by(entity="cacao").first()
    acc = database.session.query(Accounts).filter_by(entity="cacao", group=False).first()
    cc = database.session.query(CostCenter).filter_by(entity="cacao").first()
    per = database.session.query(AccountingPeriod).filter_by(fiscal_year_id=fy.id).first()

    budget = service.create_budget(
        {
            "company": "cacao",
            "ledger_id": book.id,
            "fiscal_year_id": fy.id,
            "budget_code": "VALIDATION-TEST",
            "name": "Validation Test",
            "currency_id": "NIO",
        },
        str(admin_user.id),
    )

    group_account = Accounts(
        entity="cacao",
        code="GRP-BUDGET",
        name="Grupo Presupuesto",
        active=True,
        enabled=True,
        group=True,
    )
    database.session.add(group_account)
    database.session.commit()

    with pytest.raises(BudgetError, match="No se puede presupuestar en una cuenta agrupadora"):
        service.add_budget_line(
            budget.id,
            {"account_id": group_account.id, "cost_center_id": cc.id, "period_id": per.id, "amount": 100},
            str(admin_user.id),
        )

    with pytest.raises(BudgetError, match="Centro de costo no válido"):
        service.add_budget_line(
            budget.id,
            {"account_id": acc.id, "cost_center_id": "INVALID", "period_id": per.id, "amount": 100},
            str(admin_user.id),
        )

    with pytest.raises(BudgetError, match="Unidad de negocio no válida"):
        service.add_budget_line(
            budget.id,
            {
                "account_id": acc.id,
                "cost_center_id": cc.id,
                "period_id": per.id,
                "business_unit_id": "INVALID",
                "amount": 100,
            },
            str(admin_user.id),
        )

    with pytest.raises(BudgetError, match="Proyecto no válido"):
        service.add_budget_line(
            budget.id,
            {
                "account_id": acc.id,
                "cost_center_id": cc.id,
                "period_id": per.id,
                "project_id": "INVALID",
                "amount": 100,
            },
            str(admin_user.id),
        )

    service.add_budget_line(
        budget.id,
        {"account_id": acc.id, "cost_center_id": cc.id, "period_id": per.id, "amount": 100},
        str(admin_user.id),
    )

    with pytest.raises(BudgetError, match="Ya existe una línea para esta combinación"):
        service.add_budget_line(
            budget.id,
            {"account_id": acc.id, "cost_center_id": cc.id, "period_id": per.id, "amount": 100},
            str(admin_user.id),
        )


def test_budget_import_rollback(app_ctx):
    from cacao_accounting.contabilidad.budget_import_service import BudgetImportService
    from cacao_accounting.database import BudgetImportLine

    service = BudgetService()
    import_service = BudgetImportService()
    admin_user = database.session.query(User).filter_by(user="admin").first()
    fy = database.session.query(FiscalYear).filter_by(entity="cacao").first()
    book = database.session.query(Book).filter_by(entity="cacao").first()
    acc = database.session.query(Accounts).filter_by(entity="cacao", group=False).all()
    cc = database.session.query(CostCenter).filter_by(entity="cacao").first()
    per = database.session.query(AccountingPeriod).filter_by(fiscal_year_id=fy.id).first()

    budget = service.create_budget(
        {
            "company": "cacao",
            "ledger_id": book.id,
            "fiscal_year_id": fy.id,
            "budget_code": "ROLLBACK-TEST",
            "name": "Rollback Test",
            "currency_id": "NIO",
        },
        str(admin_user.id),
    )

    # Create a batch with two lines with DIFFERENT accounts to pass validate_import
    csv_content = f"Cuenta,Centro de Costo,Unidad de Negocio,Proyecto,Descripción,{per.name},Total\n"
    csv_content += f"{acc[0].code},{cc.code},,,L1,100,100\n"
    csv_content += f"{acc[1].code},{cc.code},,,L2,200,200\n"

    # validate_import should pass
    batch = import_service.validate_import(budget.id, "test.csv", csv_content.encode("utf-8"), str(admin_user.id))
    assert batch.status == "validated"

    # Manipulate staging: set a required field to None to force a DB error on insert
    line2 = database.session.query(BudgetImportLine).filter_by(import_id=batch.id).all()[1]
    line2.amount = None  # BudgetLine.amount is NOT NULL
    database.session.commit()

    with pytest.raises(BudgetError, match="Error atómico en inserción"):
        import_service.insert_lines(batch.id, str(admin_user.id))

    # Verify rollback: no lines should be in BudgetLine for this budget
    lines = database.session.query(BudgetLine).filter_by(budget_id=budget.id).all()
    assert len(lines) == 0

    # Batch should be marked as failed
    database.session.refresh(batch)
    assert batch.status == "failed"


def test_budget_import_unknown_column(app_ctx):
    from cacao_accounting.contabilidad.budget_import_service import BudgetImportService

    service = BudgetService()
    import_service = BudgetImportService()
    admin_user = database.session.query(User).filter_by(user="admin").first()
    fy = database.session.query(FiscalYear).filter_by(entity="cacao").first()
    book = database.session.query(Book).filter_by(entity="cacao").first()

    budget = service.create_budget(
        {
            "company": "cacao",
            "ledger_id": book.id,
            "fiscal_year_id": fy.id,
            "budget_code": "UNKNOWN-COL",
            "name": "Unknown Col",
            "currency_id": "NIO",
        },
        str(admin_user.id),
    )

    csv_content = "Cuenta,Centro de Costo,UnknownColumn\n100,200,Error\n"
    with pytest.raises(BudgetError, match="Columna desconocida detectada"):
        import_service.validate_import(budget.id, "test.csv", csv_content.encode("utf-8"), str(admin_user.id))


def test_budget_report_filters_with_dimension_ids(app_ctx):
    service = BudgetService()
    admin_user = database.session.query(User).filter_by(user="admin").first()
    fy = database.session.query(FiscalYear).filter_by(entity="cacao").first()
    book = database.session.query(Book).filter_by(entity="cacao").first()
    acc = database.session.query(Accounts).filter_by(entity="cacao", group=False).first()
    cc = database.session.query(CostCenter).filter_by(entity="cacao").first()
    per = database.session.query(AccountingPeriod).filter_by(fiscal_year_id=fy.id).first()

    budget = service.create_budget(
        {
            "company": "cacao",
            "ledger_id": book.id,
            "fiscal_year_id": fy.id,
            "budget_code": "FILTER-ID-TEST",
            "name": "Filtro por ID",
            "currency_id": "NIO",
        },
        str(admin_user.id),
    )

    service.add_budget_line(
        budget.id,
        {
            "account_id": acc.id,
            "cost_center_id": cc.id,
            "period_id": per.id,
            "amount": 250,
        },
        str(admin_user.id),
    )

    report = BudgetReportService().get_real_vs_budget_report(
        {
            "company": "cacao",
            "budget_id": budget.id,
            "ledger_id": book.id,
            "fiscal_year_id": fy.id,
            "granularity": "month",
            "cost_center_id": cc.id,
        }
    )
    assert len(report.rows) >= 1
    assert report.totals["budget"] == Decimal("250")


def test_budget_report_populates_actual_and_budget_amounts(app_ctx):
    service = BudgetService()
    admin_user = database.session.query(User).filter_by(user="admin").first()
    fy = database.session.query(FiscalYear).filter_by(entity="cacao").first()
    book = database.session.query(Book).filter_by(entity="cacao").first()
    acc = database.session.query(Accounts).filter_by(entity="cacao", group=False).first()
    cc = database.session.query(CostCenter).filter_by(entity="cacao").first()
    per = database.session.query(AccountingPeriod).filter_by(fiscal_year_id=fy.id).first()

    unit = Unit(entity="cacao", code="BU-TEST", name="Unidad Test")
    project = Project(entity="cacao", code="PRJ-TEST", name="Proyecto Test", enabled=True, start=per.start)
    database.session.add_all([unit, project])
    database.session.flush()

    budget = service.create_budget(
        {
            "company": "cacao",
            "ledger_id": book.id,
            "fiscal_year_id": fy.id,
            "budget_code": "REPORT-MAP-TEST",
            "name": "Reporte Real vs Presupuesto",
            "currency_id": "NIO",
        },
        str(admin_user.id),
    )

    service.add_budget_line(
        budget.id,
        {
            "account_id": acc.id,
            "cost_center_id": cc.id,
            "business_unit_id": unit.id,
            "project_id": project.id,
            "period_id": per.id,
            "amount": 250,
        },
        str(admin_user.id),
    )

    gl_entry = GLEntry(
        company="cacao",
        ledger_id=book.id,
        account_id=acc.id,
        account_code=acc.code,
        cost_center_code=cc.code,
        unit_code=unit.code,
        project_code=project.code,
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

    report = BudgetReportService().get_real_vs_budget_report(
        {
            "company": "cacao",
            "budget_id": budget.id,
            "ledger_id": book.id,
            "fiscal_year_id": fy.id,
            "granularity": "month",
            "cost_center_id": cc.id,
            "business_unit_id": unit.id,
            "project_id": project.id,
        }
    )

    assert len(report.rows) == 1
    row = report.rows[0].values
    assert row["budget"] == Decimal("250")
    assert row["actual"] == Decimal("300")
    assert row["variance"] == Decimal("50")
    assert report.totals["budget"] == Decimal("250")
    assert report.totals["actual"] == Decimal("300")
