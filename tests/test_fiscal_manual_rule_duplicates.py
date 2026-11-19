# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1008: las líneas fiscales manuales no pueden repetir su identificador.

El motor indexa reglas por ``rule_id``; dos conceptos con el mismo identificador
hacían que una línea reemplazara a la otra en el preview y el total persistido
divergiera del payload original.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, DocumentTaxLine, DocumentTaxSummary, Entity, database

DOCUMENTO = "sales_invoice"


@pytest.fixture
def fiscal_duplicados():
    """Aplicación aislada sin reglas fiscales persistidas."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name="Compañía Alfa",
                    tax_id="J-ALFA",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _linea(rule_id: str, concept: str, amount: str) -> dict[str, str | bool]:
    """Construye una línea fiscal manual representativa."""
    return {
        "source_rule_id": rule_id,
        "manual": True,
        "concept": concept,
        "type": "tax",
        "calculation_method": "fixed",
        "amount": amount,
    }


def _payload(tax_lines: list[dict[str, str | bool]]) -> dict[str, object]:
    """Payload mínimo de factura de venta con las líneas fiscales indicadas."""
    return {
        "document_type": DOCUMENTO,
        "company": "alpha",
        "posting_date": "2026-05-10",
        "currency": "NIO",
        "lines": [{"qty": 1, "rate": 100}],
        "tax_lines": tax_lines,
    }


def test_preview_rechaza_identificadores_manuales_duplicados(fiscal_duplicados):
    """Dos conceptos con el mismo ID fallan antes de calcular el preview."""
    from cacao_accounting.fiscal_preview_service import fiscal_preview

    with fiscal_duplicados.app_context():
        with pytest.raises(ValueError, match="repetir el identificador"):
            fiscal_preview(_payload([_linea("MANUAL-DUP", "IVA", "10"), _linea("MANUAL-DUP", "DAI", "20")]))


def test_preview_con_identificadores_unicos_conserva_ambas_lineas(fiscal_duplicados):
    """El control positivo mantiene los dos conceptos y el total correcto."""
    from cacao_accounting.fiscal_preview_service import fiscal_preview

    with fiscal_duplicados.app_context():
        result = fiscal_preview(_payload([_linea("MANUAL-IVA", "IVA", "10"), _linea("MANUAL-DAI", "DAI", "20")]))

    assert {line["source_rule_id"] for line in result["tax_lines"]} == {"MANUAL-IVA", "MANUAL-DAI"}
    assert Decimal(result["summary"]["grand_total"]) == Decimal("130")
    assert result["errors"] == []


def test_total_persistible_rechaza_identificadores_duplicados(fiscal_duplicados):
    """El cálculo server-side del total usa la misma validación que el preview."""
    from cacao_accounting.fiscal_persistence_service import calculate_document_total_with_taxes

    class _Documento:
        company = "alpha"
        tax_template_id = None

    with fiscal_duplicados.app_context():
        with pytest.raises(ValueError, match="repetir el identificador"):
            calculate_document_total_with_taxes(
                _Documento(),
                Decimal("100"),
                [],
                tax_lines_payload=[_linea("MANUAL-DUP", "IVA", "10"), _linea("MANUAL-DUP", "DAI", "20")],
            )


def test_snapshot_rechaza_duplicados_sin_persistir_evidencia(fiscal_duplicados):
    """El snapshot no borra ni escribe filas cuando el payload es ambiguo."""
    from cacao_accounting.fiscal_persistence_service import persist_document_fiscal_snapshot

    with fiscal_duplicados.app_context():
        with pytest.raises(ValueError, match="repetir el identificador"):
            persist_document_fiscal_snapshot(
                company="alpha",
                document_type=DOCUMENTO,
                document_id="doc-duplicado",
                currency="NIO",
                tax_lines=[_linea("MANUAL-DUP", "IVA", "10"), _linea("MANUAL-DUP", "DAI", "20")],
                tax_summary={"subtotal": "100", "grand_total": "130"},
            )
        assert (
            database.session.execute(
                database.select(DocumentTaxSummary).filter_by(document_id="doc-duplicado")
            ).scalar_one_or_none()
            is None
        )
        assert (
            database.session.execute(database.select(DocumentTaxLine).filter_by(document_tax_summary_id="doc-duplicado"))
            .scalars()
            .all()
            == []
        )


def test_snapshot_con_identificadores_unicos_persiste_ambas_lineas(fiscal_duplicados):
    """El control positivo conserva las dos líneas en el snapshot fiscal."""
    from cacao_accounting.fiscal_persistence_service import load_document_fiscal_lines, persist_document_fiscal_snapshot

    with fiscal_duplicados.app_context():
        persist_document_fiscal_snapshot(
            company="alpha",
            document_type=DOCUMENTO,
            document_id="doc-valido",
            currency="NIO",
            tax_lines=[_linea("MANUAL-IVA", "IVA", "10"), _linea("MANUAL-DAI", "DAI", "20")],
            tax_summary={"subtotal": "100", "grand_total": "130"},
        )
        database.session.commit()
        lineas = load_document_fiscal_lines(DOCUMENTO, "doc-valido")

    assert [line.rule_id for line in lineas] == ["MANUAL-IVA", "MANUAL-DAI"]


def test_motor_fiscal_reporta_identificadores_duplicados():
    """El motor rechaza contextos ambiguos aunque lleguen sin pasar por el preview."""
    from cacao_accounting.accounting_engine.common.context import (
        CalculationContext,
        ItemContext,
        TaxRuleContext,
    )
    from cacao_accounting.accounting_engine.fiscal.engine import FiscalEngine

    context = CalculationContext(
        company_id="alpha",
        document_type=DOCUMENTO,
        event_type="sales_invoice_confirmed",
        transaction_direction="sales",
        transaction_date=date(2026, 5, 10),
        posting_date=date(2026, 5, 10),
        party_type="customer",
        party_id="CUSTOMER",
        currency="NIO",
        company_currency="NIO",
        items=[
            ItemContext(
                line_id="line-1",
                item_id="item-1",
                description="Producto",
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
                gross_amount=Decimal("100"),
                net_amount=Decimal("100"),
            )
        ],
        tax_rules=[
            TaxRuleContext(
                rule_id="MANUAL-DUP",
                name="IVA",
                concept="IVA",
                tax_type="tax",
                calculation_method="fixed",
                amount=Decimal("10"),
            ),
            TaxRuleContext(
                rule_id="MANUAL-DUP",
                name="DAI",
                concept="DAI",
                tax_type="tax",
                calculation_method="fixed",
                amount=Decimal("20"),
            ),
        ],
    )

    result = FiscalEngine().calculate(context)

    assert result.tax_lines == []
    assert any("repetir el identificador" in error for error in result.errors)
