# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Errores del preview fiscal y rango conservado en el drilldown.

Escenario de negocio (R2R):
- #1943: una respuesta con errors se presentaba como preview válido.
- #1939: el drilldown perdía accounting_period_from/to del reporte padre.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, database
from cacao_accounting.reportes.helpers import _build_row_metadata
from cacao_accounting.reportes.services import FinancialReportFilters


def _crear_app():
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
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                Modules(module="sales", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_preview_fiscal_con_errores_responde_422(monkeypatch):
    """#1943: el API no devuelve 200 cuando el motor reporta errores."""
    import importlib

    application = _crear_app()
    try:
        api_module = importlib.import_module("cacao_accounting.api")
        monkeypatch.setattr(
            api_module,
            "fiscal_preview",
            lambda payload: {
                "profile": {"event_type": "sales_invoice_confirmed"},
                "tax_lines": [],
                "summary": {"grand_total": 100},
                "errors": ["Circular dependency detected in tax rules."],
            },
        )
        client = _cliente(application)
        respuesta = client.post(
            "/api/fiscal/preview",
            json={"company": "cacao", "document_type": "sales_invoice"},
        )

        assert respuesta.status_code == 422
        assert respuesta.get_json()["errors"] == ["Circular dependency detected in tax rules."]
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_preview_fiscal_valido_sigue_respondiendo_200(monkeypatch):
    """#1943: un cálculo sin errores mantiene el contrato 200."""
    import importlib

    application = _crear_app()
    try:
        api_module = importlib.import_module("cacao_accounting.api")
        monkeypatch.setattr(
            api_module,
            "fiscal_preview",
            lambda payload: {
                "profile": {"event_type": "sales_invoice_confirmed"},
                "tax_lines": [{"concept": "IVA", "amount": "15.00"}],
                "summary": {"grand_total": 115},
                "errors": [],
            },
        )
        client = _cliente(application)
        respuesta = client.post(
            "/api/fiscal/preview",
            json={"company": "cacao", "document_type": "sales_invoice"},
        )

        assert respuesta.status_code == 200
        assert respuesta.get_json()["errors"] == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_el_cliente_muestra_errores_del_preview():
    """#1943: el JS no aplica un preview con errors como si fuera válido."""
    js = Path("cacao_accounting/static/js/transaction-form.js").read_text(encoding="utf-8")

    assert "data.errors" in js
    assert "this.taxCharges.error = errors.join(' ')" in js


def test_drilldown_conserva_el_rango_contable():
    """#1939: el enlace de detalle incluye los períodos del reporte padre."""
    application = _crear_app()
    try:
        with application.test_request_context("/"):
            metadata = _build_row_metadata(
                [{"account_code": "1101", "debit": 10, "credit": 0}],
                FinancialReportFilters(
                    company="cacao",
                    ledger="LEDGER-1",
                    period_from="PER-A",
                    period_to="PER-B",
                ),
            )

        url = metadata[0]["drilldown_url"]
        assert "accounting_period_from=PER-A" in url
        assert "accounting_period_to=PER-B" in url
        assert "company=cacao" in url
        assert "ledger=LEDGER-1" in url
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
