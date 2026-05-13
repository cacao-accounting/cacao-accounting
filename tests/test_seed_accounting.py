# SPDX-License-Identifier: Apache-2.0
import pytest
from decimal import Decimal
from cacao_accounting import create_app
from cacao_accounting.database import database, Book, GLEntry, Unit, CostCenter, Project, ExchangeRate
from cacao_accounting.datos import base_data, dev_data
from cacao_accounting.reportes.services import (
    FinancialReportFilters,
    get_balance_sheet_report,
    get_income_statement_report,
    get_trial_balance_report
)

@pytest.fixture(scope="function")
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test_key"
    })
    with app.app_context():
        database.create_all()
        base_data("admin", "admin", carga_rapida=True)
        dev_data()
        yield app
        database.session.remove()
        database.drop_all()

def test_libros_contables(app):
    with app.app_context():
        # La empresa cacao debe tener 3 libros
        libros = database.session.execute(database.select(Book).filter_by(entity="cacao")).scalars().all()
        codigos_libros = [l.code for l in libros]
        assert "FISC" in codigos_libros
        assert "FIN" in codigos_libros
        assert "MGMT" in codigos_libros

        # Verificar monedas de los libros
        libro_fisc = database.session.execute(database.select(Book).filter_by(entity="cacao", code="FISC")).scalar_one()
        assert libro_fisc.currency == "NIO"
        libro_fin = database.session.execute(database.select(Book).filter_by(entity="cacao", code="FIN")).scalar_one()
        assert libro_fin.currency == "USD"
        libro_mgmt = database.session.execute(database.select(Book).filter_by(entity="cacao", code="MGMT")).scalar_one()
        assert libro_mgmt.currency == "EUR"

def test_unidades_centros_proyectos(app):
    with app.app_context():
        # Unidades
        u = database.session.execute(database.select(Unit).filter_by(entity="cacao", code="logistica")).scalar_one_or_none()
        assert u is not None

        # Centros de Costos
        cc_adm = database.session.execute(database.select(CostCenter).filter_by(entity="cacao", code="ADM")).scalar_one_or_none()
        assert cc_adm is not None

        # Proyectos
        p = database.session.execute(database.select(Project).filter_by(entity="cacao", code="EXPANSION")).scalar_one_or_none()
        assert p is not None

def test_tasas_de_cambio(app):
    with app.app_context():
        # Deben existir tasas para USD y EUR hoy
        tasa_usd = database.session.execute(database.select(ExchangeRate).filter_by(origin="NIO", destination="USD")).scalars().first()
        assert tasa_usd is not None
        tasa_eur = database.session.execute(database.select(ExchangeRate).filter_by(origin="NIO", destination="EUR")).scalars().first()
        assert tasa_eur is not None

def test_ledger_multimoneda(app):
    with app.app_context():
        # Obtener IDs de libros
        fisc_id = database.session.execute(database.select(Book.id).filter_by(entity="cacao", code="FISC")).scalar_one()
        fin_id = database.session.execute(database.select(Book.id).filter_by(entity="cacao", code="FIN")).scalar_one()
        mgmt_id = database.session.execute(database.select(Book.id).filter_by(entity="cacao", code="MGMT")).scalar_one()

        # Verificar que existen entradas en el ledger para los diferentes libros
        # Libro FISC (NIO)
        entries_fisc = database.session.execute(database.select(GLEntry).filter_by(company="cacao", ledger_id=fisc_id)).scalars().all()
        assert len(entries_fisc) > 0
        for entry in entries_fisc:
            assert entry.company_currency == "NIO"

        # Libro FIN (USD)
        entries_fin = database.session.execute(database.select(GLEntry).filter_by(company="cacao", ledger_id=fin_id)).scalars().all()
        assert len(entries_fin) > 0
        for entry in entries_fin:
            assert entry.account_currency == "USD"

        # Libro MGMT (EUR)
        entries_mgmt = database.session.execute(database.select(GLEntry).filter_by(company="cacao", ledger_id=mgmt_id)).scalars().all()
        assert len(entries_mgmt) > 0
        for entry in entries_mgmt:
            assert entry.account_currency == "EUR"

def test_reportes_financieros(app):
    with app.app_context():
        # Filtros base para reportes
        filters = FinancialReportFilters(company="cacao", ledger="FISC")

        # 1. Balanza de Comprobación
        trial_balance = get_trial_balance_report(filters)
        assert trial_balance.totals["difference"] == 0
        assert trial_balance.totals["debit"] > 0

        # 2. Balance General
        balance_sheet = get_balance_sheet_report(filters)
        # Activos = Pasivos + Patrimonio (la diferencia debe ser 0)
        assert abs(balance_sheet.totals["difference"]) < Decimal("0.0001")
        assert balance_sheet.totals["assets"] > 0

        # 3. Estado de Resultados
        income_statement = get_income_statement_report(filters)
        # En el seed actual solo hay saldos iniciales en cuentas de activo y patrimonio
        # pero validamos que el reporte se ejecute sin errores y balancee.
        assert "net_profit" in income_statement.totals
