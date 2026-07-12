# SPDX-License-Identifier: Apache-2.0

import pytest
import io
from datetime import date
from decimal import Decimal

from z_func import init_test_db
from cacao_accounting import create_app
from cacao_accounting.database import (
    database as db,
    CashForecast,
    CashForecastEntry,
    FiscalYear,
)
from cacao_accounting.bancos.cash_forecast_service import (
    generate_periods,
    get_cash_forecast_matrix,
    get_forecast_comparison,
)
from cacao_accounting.runtime_mode import is_desktop_mode

# Create custom test app
test_app = create_app(
    {
        "TESTING": True,
        "SECRET_KEY": "test_secret_for_cash_forecast",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "DEBUG": True,
        "PRESERVE_CONTEXT_ON_EXCEPTION": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
    }
)


@pytest.fixture(scope="module", autouse=True)
def setup_test_data(request):
    with test_app.app_context():
        init_test_db(test_app)

        # Ensure we have a fiscal year
        fy = db.session.query(FiscalYear).filter_by(entity="cacao").first()
        if not fy:
            fy = FiscalYear(
                entity="cacao",
                name="2026",
                year_start_date=date(2026, 1, 1),
                year_end_date=date(2026, 12, 31),
                is_closed=False,
            )
            db.session.add(fy)
            db.session.commit()


def test_cash_forecast_models():
    """Test model creation and validations."""
    with test_app.app_context():
        fy = db.session.query(FiscalYear).filter_by(entity="cacao").first()
        assert fy is not None

        # Create forecast
        forecast = CashForecast(
            version="V-TEST-01",
            description="Escenario de Pruebas",
            fiscal_year_id=fy.id,
            company="cacao",
            periodicity="monthly",
            status="Draft",
        )
        db.session.add(forecast)
        db.session.commit()

        assert forecast.id is not None
        assert forecast.status == "Draft"

        # Create forecast entry
        entry = CashForecastEntry(
            forecast_id=forecast.id,
            type="Income",
            concept="Venta de Activo Fijo",
            currency="NIO",
            amount=Decimal("15000.00"),
            estimated_date=date(2026, 6, 15),
            notes="Prueba de nota",
        )
        db.session.add(entry)
        db.session.commit()

        assert entry.id is not None
        assert entry.amount == Decimal("15000.00")

        # Clean up
        db.session.delete(entry)
        db.session.delete(forecast)
        db.session.commit()


def test_period_generation():
    """Test dividing fiscal year into weekly and monthly periods."""
    with test_app.app_context():
        fy = db.session.query(FiscalYear).filter_by(entity="cacao").first()

        # Test monthly
        monthly_periods = generate_periods(fy, "monthly")
        assert len(monthly_periods) == 12
        assert monthly_periods[0]["name"] == "January 2026"
        assert monthly_periods[0]["start_date"] == date(2026, 1, 1)
        assert monthly_periods[0]["end_date"] == date(2026, 1, 31)

        # Test weekly
        weekly_periods = generate_periods(fy, "weekly")
        assert len(weekly_periods) >= 52


def test_cash_forecast_matrix_calculation():
    """Test YTD cash flow calculations including Real, Current, and Projected zones."""
    with test_app.app_context():
        fy = db.session.query(FiscalYear).filter_by(entity="cacao").first()

        forecast = CashForecast(
            version="V-TEST-MATRIX",
            description="Matriz test",
            fiscal_year_id=fy.id,
            company="cacao",
            periodicity="monthly",
            status="Draft",
        )
        db.session.add(forecast)
        db.session.flush()

        # Add some manual entries
        # An income projection in August 2026
        entry_in = CashForecastEntry(
            forecast_id=forecast.id,
            type="Income",
            concept="Subvención",
            currency="NIO",
            amount=Decimal("5000.00"),
            estimated_date=date(2026, 8, 10),
        )
        # An expense projection in August 2026
        entry_out = CashForecastEntry(
            forecast_id=forecast.id,
            type="Expense",
            concept="Mantenimiento",
            currency="NIO",
            amount=Decimal("2000.00"),
            estimated_date=date(2026, 8, 20),
        )
        db.session.add_all([entry_in, entry_out])
        db.session.commit()

        # We set today to July 11, 2026
        today = date(2026, 7, 11)

        # Calculate matrix
        matrix = get_cash_forecast_matrix("cacao", forecast.id, today_date=today)

        assert len(matrix) == 12

        # January to June are "Real" (past periods)
        for i in range(6):
            assert matrix[i]["zone"] == "Real"

        # July is "Current"
        assert matrix[6]["period"] == "July 2026"
        assert matrix[6]["zone"] == "Current"

        # August is "Projected"
        assert matrix[7]["period"] == "August 2026"
        assert matrix[7]["zone"] == "Projected"
        assert matrix[7]["manual_inflow"] == Decimal("5000.00")
        assert matrix[7]["manual_outflow"] == Decimal("2000.00")

        # Clean up
        db.session.delete(entry_in)
        db.session.delete(entry_out)
        db.session.delete(forecast)
        db.session.commit()


def test_forecast_comparison():
    """Test comparing two forecast scenarios."""
    with test_app.app_context():
        fy = db.session.query(FiscalYear).filter_by(entity="cacao").first()

        f1 = CashForecast(
            version="BASE-CASE",
            fiscal_year_id=fy.id,
            company="cacao",
            periodicity="monthly",
            status="Draft",
        )
        f2 = CashForecast(
            version="COMPARE-CASE",
            fiscal_year_id=fy.id,
            company="cacao",
            periodicity="monthly",
            status="Draft",
        )
        db.session.add_all([f1, f2])
        db.session.flush()

        entry_f1 = CashForecastEntry(
            forecast_id=f1.id,
            type="Income",
            concept="Capital",
            currency="NIO",
            amount=Decimal("10000.00"),
            estimated_date=date(2026, 9, 15),
        )
        entry_f2 = CashForecastEntry(
            forecast_id=f2.id,
            type="Income",
            concept="Capital",
            currency="NIO",
            amount=Decimal("15000.00"),
            estimated_date=date(2026, 9, 15),
        )
        db.session.add_all([entry_f1, entry_f2])
        db.session.commit()

        comparison = get_forecast_comparison("cacao", f1.id, f2.id, today_date=date(2026, 7, 11))

        # Check September 2026 (index 8)
        sept = [row for row in comparison if row["period"] == "September 2026"][0]
        assert sept["base_manual_inflow"] == Decimal("10000.00")
        assert sept["compare_manual_inflow"] == Decimal("15000.00")
        assert sept["variance_manual_inflow"] == Decimal("5000.00")

        # Clean up
        db.session.delete(entry_f1)
        db.session.delete(entry_f2)
        db.session.delete(f1)
        db.session.delete(f2)
        db.session.commit()


@pytest.mark.skipif(is_desktop_mode(), reason="Requires cloud mode")
def test_routes_list_and_details():
    """Test HTTP routes for listing and displaying forecast details."""
    with test_app.test_client() as client:
        # Simulate login
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        with test_app.app_context():
            fy = db.session.query(FiscalYear).filter_by(entity="cacao").first()

            # Create a test forecast
            forecast = CashForecast(
                version="WEB-TEST",
                description="Vista web",
                fiscal_year_id=fy.id,
                company="cacao",
                periodicity="monthly",
                status="Draft",
            )
            db.session.add(forecast)
            db.session.commit()
            forecast_id = forecast.id

        # 1. Test list view
        response = client.get("/cash_management/cash-forecast/list?company=cacao")
        assert response.status_code == 200
        assert b"Pron\xc3\xb3sticos de Flujo de Caja" in response.data

        # 2. Test detail view
        response = client.get(f"/cash_management/cash-forecast/{forecast_id}")
        assert response.status_code == 200
        assert b"WEB-TEST" in response.data

        # 3. Test adding entry via POST
        response = client.post(
            f"/cash_management/cash-forecast/{forecast_id}/entry/add",
            data={
                "type": "Income",
                "concept": "Cobro Extraordinario",
                "currency": "NIO",
                "amount": "800.00",
                "estimated_date": "2026-10-10",
                "notes": "Observacion de prueba",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        with test_app.app_context():
            # Verify entry was saved
            entry = (
                db.session.query(CashForecastEntry).filter_by(forecast_id=forecast_id).first()
            )
            assert entry is not None
            assert entry.concept == "Cobro Extraordinario"
            assert entry.amount == Decimal("800.00")
            entry_id = entry.id

        # 4. Test status transitions (Draft -> Approved)
        response = client.post(
            f"/cash_management/cash-forecast/{forecast_id}/approve",
            follow_redirects=True,
        )
        assert response.status_code == 200

        with test_app.app_context():
            forecast_updated = db.session.get(CashForecast, forecast_id)
            assert forecast_updated.status == "Approved"

        # 5. Verify draft-only edits/deletes are locked
        response = client.post(
            f"/cash_management/cash-forecast/{forecast_id}/entry/{entry_id}/delete",
            follow_redirects=True,
        )
        assert response.status_code == 200
        # Since status is Approved, delete should fail / be ignored, and entry remains in DB
        with test_app.app_context():
            entry_still_exists = db.session.get(CashForecastEntry, entry_id)
            assert entry_still_exists is not None

        # Clean up
        with test_app.app_context():
            forecast_del = db.session.get(CashForecast, forecast_id)
            if forecast_del:
                db.session.delete(forecast_del)
                db.session.commit()


@pytest.mark.skipif(is_desktop_mode(), reason="Requires cloud mode")
def test_routes_import_entries():
    """Test importing manual entries from CSV and XLSX file."""
    with test_app.test_client() as client:
        # Simulate login
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        with test_app.app_context():
            fy = db.session.query(FiscalYear).filter_by(entity="cacao").first()
            # Create a test forecast in draft mode
            forecast = CashForecast(
                version="IMPORT-TEST",
                description="Import test",
                fiscal_year_id=fy.id,
                company="cacao",
                periodicity="monthly",
                status="Draft",
            )
            db.session.add(forecast)
            db.session.commit()
            forecast_id = forecast.id

        # 1. Test CSV Import
        csv_data = (
            "type,concept,currency,amount,estimated_date,notes\n"
            "Income,Inyeccion Capital,NIO,25000.00,2026-05-15,Socio A\n"
            "Expense,Prestamo Banco,NIO,5000.00,2026-05-20,Cuota 1"
        )
        data = {"file": (io.BytesIO(csv_data.encode("utf-8")), "test_forecast.csv")}
        response = client.post(
            f"/cash_management/cash-forecast/{forecast_id}/entry/import",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Se importaron 2 proyecciones manuales con" in response.data

        with test_app.app_context():
            entries = (
                db.session.query(CashForecastEntry).filter_by(forecast_id=forecast_id).all()
            )
            assert len(entries) == 2
            # Check fields
            entries_by_concept = {e.concept: e for e in entries}
            assert "Inyeccion Capital" in entries_by_concept
            assert entries_by_concept["Inyeccion Capital"].amount == Decimal("25000.00")
            assert "Prestamo Banco" in entries_by_concept
            assert entries_by_concept["Prestamo Banco"].amount == Decimal("5000.00")

        # 2. Test XLSX Import
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        # Write headers
        ws.append(["type", "concept", "currency", "amount", "estimated_date", "notes"])
        ws.append(["Income", "Excel Income", "NIO", 12000.00, "2026-06-01", "From Excel"])

        file_stream = io.BytesIO()
        wb.save(file_stream)
        file_stream.seek(0)

        data_xlsx = {"file": (file_stream, "test_forecast.xlsx")}
        response = client.post(
            f"/cash_management/cash-forecast/{forecast_id}/entry/import",
            data=data_xlsx,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Se importaron 1 proyecciones manuales con" in response.data

        with test_app.app_context():
            entries = (
                db.session.query(CashForecastEntry).filter_by(forecast_id=forecast_id).all()
            )
            # 2 from CSV + 1 from XLSX = 3
            assert len(entries) == 3
            xlsx_entry = [e for e in entries if e.concept == "Excel Income"][0]
            assert xlsx_entry.amount == Decimal("12000.00")
            assert xlsx_entry.estimated_date == date(2026, 6, 1)

        # Clean up
        with test_app.app_context():
            forecast_del = db.session.get(CashForecast, forecast_id)
            if forecast_del:
                db.session.delete(forecast_del)
                db.session.commit()


def test_desktop_mode_redirect(monkeypatch):
    """Test that if in desktop mode, the routes redirect with warning."""
    with test_app.test_client() as client:
        # Login
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # Mock is_desktop_mode to return True
        import sys

        cf_module = sys.modules["cacao_accounting.bancos.cash_forecast"]
        monkeypatch.setattr(cf_module, "is_desktop_mode", lambda: True)

        response = client.get("/cash_management/cash-forecast/list", follow_redirects=True)
        assert response.status_code == 200
        # Check that we redirected back to bancos dashboard and warning is flashed
        assert (
            b"Proyecci\xc3\xb3n de flujo de caja no disponible en modo DESKTOP" in response.data
        )


@pytest.mark.skipif(is_desktop_mode(), reason="Requires cloud mode")
def test_edit_manual_entry_route():
    """Test that editing a manual entry via its dedicated POST endpoint works."""
    with test_app.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        with test_app.app_context():
            fy = db.session.query(FiscalYear).filter_by(entity="cacao").first()
            forecast = CashForecast(
                version="EDIT-ROUTE-TEST",
                description="Edit test",
                fiscal_year_id=fy.id,
                company="cacao",
                periodicity="monthly",
                status="Draft",
            )
            db.session.add(forecast)
            db.session.flush()

            entry = CashForecastEntry(
                forecast_id=forecast.id,
                type="Income",
                concept="Original Concept",
                currency="NIO",
                amount=Decimal("100.00"),
                estimated_date=date(2026, 5, 10),
            )
            db.session.add(entry)
            db.session.commit()
            forecast_id = forecast.id
            entry_id = entry.id

        # Perform the edit via POST
        response = client.post(
            f"/cash_management/cash-forecast/{forecast_id}/entry/{entry_id}/edit",
            data={
                "type": "Expense",
                "concept": "Updated Concept",
                "currency": "NIO",
                "amount": "250.00",
                "estimated_date": "2026-05-12",
                "notes": "Edited notes",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        with test_app.app_context():
            updated_entry = db.session.get(CashForecastEntry, entry_id)
            assert updated_entry.type == "Expense"
            assert updated_entry.concept == "Updated Concept"
            assert updated_entry.amount == Decimal("250.00")
            assert updated_entry.estimated_date == date(2026, 5, 12)
            assert updated_entry.notes == "Edited notes"

            # Clean up
            db.session.delete(updated_entry)
            db.session.delete(db.session.get(CashForecast, forecast_id))
            db.session.commit()


@pytest.mark.skipif(is_desktop_mode(), reason="Requires cloud mode")
def test_manual_entries_dashboard_route():
    """Test that the new /cash-forecast/manual-entries route renders and list entries."""
    with test_app.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        with test_app.app_context():
            fy = db.session.query(FiscalYear).filter_by(entity="cacao").first()
            forecast = CashForecast(
                version="DASHBOARD-TEST",
                description="Dashboard list test",
                fiscal_year_id=fy.id,
                company="cacao",
                periodicity="monthly",
                status="Draft",
            )
            db.session.add(forecast)
            db.session.flush()

            entry = CashForecastEntry(
                forecast_id=forecast.id,
                type="Income",
                concept="Visible Concept",
                currency="NIO",
                amount=Decimal("150.00"),
                estimated_date=date(2026, 6, 12),
            )
            db.session.add(entry)
            db.session.commit()
            forecast_id = forecast.id
            entry_id = entry.id

        response = client.get(f"/cash_management/cash-forecast/manual-entries?company=cacao&forecast_id={forecast_id}")
        assert response.status_code == 200
        assert b"Forecast de Entradas manuales" in response.data
        assert b"Visible Concept" in response.data

        # Clean up
        with test_app.app_context():
            db.session.delete(db.session.get(CashForecastEntry, entry_id))
            db.session.delete(db.session.get(CashForecast, forecast_id))
            db.session.commit()


def test_budget_desktop_mode_redirect(monkeypatch):
    """Test that if in desktop mode, the budget routes redirect with warning."""
    with test_app.test_client() as client:
        # Login
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})

        # Mock is_desktop_mode to return True
        import sys

        bp_module = sys.modules["cacao_accounting.contabilidad.presupuesto"]
        monkeypatch.setattr(bp_module, "is_desktop_mode", lambda: True)

        response = client.get("/accounting/presupuestos/list", follow_redirects=True)
        assert response.status_code == 200
        # Check that we redirected back to contabilidad dashboard and warning is flashed
        assert (
            b"Gesti\xc3\xb3n de presupuesto no disponible en modo DESKTOP" in response.data
        )
