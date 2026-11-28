# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La exportación neutraliza fórmulas precedidas por controles.

Escenario de negocio (issue #1664): una descripción importada como
``"\\n=1+1"`` llegaba al CSV sin prefijo de texto; las hojas de cálculo pueden
interpretar el salto de línea y ejecutar la fórmula.
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Bank, BankAccount, Currency, Entity, database
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter
from cacao_accounting.reportes.helpers import _export_operational_report, _spreadsheet_value
from cacao_accounting.reportes.services import BankingFilters, get_bank_movement_detail


@pytest.mark.parametrize(
    "valor",
    ["=1+1", "+cmd", "-2+3", "@SUM(A1)", "\n=1+1", "\r=1+1", "\t+cmd", " \u00a0@SUM(A1)", "\ufeff=1+1"],
)
def test_neutraliza_formulas_con_prefijos_de_control(valor):
    """El apóstrofo queda como primer carácter de la celda."""
    resultado = _spreadsheet_value(valor)

    assert isinstance(resultado, str)
    assert resultado.startswith("'")
    assert resultado[1:] == valor


def test_conserva_texto_normal_y_valores_no_texto():
    """No altera descripciones legítimas ni tipos numéricos."""
    assert _spreadsheet_value("Pago de servicios") == "Pago de servicios"
    assert _spreadsheet_value("Fecha 2026-10-15") == "Fecha 2026-10-15"
    assert _spreadsheet_value(Decimal("12.50")) == Decimal("12.50")
    assert _spreadsheet_value(None) is None


def test_extracto_importado_exporta_remarks_como_texto_literal():
    """La descripción del extracto queda inerte en el CSV del reporte bancario."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    descripcion = "\n=1+1"
    fecha = date(2026, 10, 15)

    try:
        with application.app_context():
            database.create_all()
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
            database.session.flush()
            database.session.add(
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                )
            )
            database.session.flush()
            bank = Bank(name="Banco de prueba", is_active=True)
            database.session.add(bank)
            database.session.flush()
            account = BankAccount(
                company="cacao",
                bank_id=bank.id,
                account_name="Cuenta de prueba",
                account_no="TEST-1664",
                currency="NIO",
                is_active=True,
            )
            database.session.add(account)
            database.session.commit()

            row = {
                "bank_account_id": account.id,
                "posting_date": fecha.isoformat(),
                "reference_number": "EXT-1664",
                "description": descripcion,
                "deposit": "25.00",
                "withdrawal": None,
            }
            adapter = BankStatementAdapter()
            assert adapter.validate_row(row) == []
            adapter.persist_document(adapter.build_document([row], {"company_id": "cacao"}))
            database.session.commit()

            report = get_bank_movement_detail(BankingFilters(company="cacao", date_from=fecha, date_to=fecha))
            assert len(report.rows) == 1
            assert report.rows[0].values["remarks"] == descripcion

            with application.test_request_context("/reports/bank-movement?export=csv"):
                response = _export_operational_report(report, "bank-movement", "Movimientos", {})

            exported_csv = b"".join(response.response).decode("utf-8")
            response.close()
            exported_rows = list(csv.reader(StringIO(exported_csv)))
            remarks_column = report.columns.index("remarks")

            assert exported_rows[1][remarks_column] == "'" + descripcion
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
