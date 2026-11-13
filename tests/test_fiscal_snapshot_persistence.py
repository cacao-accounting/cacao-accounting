# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Reconstrucción del total fiscal desde líneas canónicas persistentes.

Escenario de negocio (issue #1023): dos líneas canónicas del mismo
concepto (tasas fijas de 10 y 8) alimentan una regla proporcional por
base acumulada (10%); el total contable del documento debe coincidir
con la suma reconstruible desde las líneas persistidas, de lo contrario
el asiento fiscal no concilia con el total aprobado.
"""

from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

SUBTOTAL = Decimal("100")


@pytest.fixture
def fiscal_empresa():
    """Aplicación de prueba con compañía, UOM/artículo y tres reglas fiscales."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        from cacao_accounting.database import Currency, Entity, TaxRule

        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                TaxRule(
                    company="cacao",
                    name="Tasa fija mayor",
                    concept="TASA_FIJA",
                    calculation_method="fixed",
                    amount=Decimal("10"),
                    sequence=10,
                    participates_in_next_base=True,
                ),
                TaxRule(
                    company="cacao",
                    name="Tasa fija menor",
                    concept="TASA_FIJA",
                    calculation_method="fixed",
                    amount=Decimal("8"),
                    sequence=20,
                    participates_in_next_base=True,
                ),
                TaxRule(
                    company="cacao",
                    name="Proporcional sobre tasas fijas",
                    concept="PROPORCIONAL",
                    calculation_method="percentage",
                    rate=Decimal("10"),
                    base_mode="accumulated",
                    include_concepts="TASA_FIJA",
                    sequence=30,
                ),
            ]
        )
        database.session.commit()
        reglas = {regla.name: regla.id for regla in database.session.execute(database.select(TaxRule)).scalars().all()}
    yield application, reglas
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _lineas_fiscales(reglas: dict) -> list[dict]:
    """Las tres líneas fiscales del documento en el orden configurado."""
    return [
        {"rule_id": reglas["Tasa fija mayor"]},
        {"rule_id": reglas["Tasa fija menor"]},
        {"rule_id": reglas["Proporcional sobre tasas fijas"]},
    ]


def test_el_total_fiscal_suma_todas_las_lineas_del_mismo_concepto(fiscal_empresa):
    """El total contable incluye ambas tasas fijas (10 + 8) y el 10% sobre su acumulado."""
    application, reglas = fiscal_empresa
    with application.app_context():
        from cacao_accounting.database import SalesInvoice
        from cacao_accounting.fiscal_persistence_service import calculate_document_total_with_taxes

        documento_sin_plantilla = SalesInvoice(company="cacao")
        total = calculate_document_total_with_taxes(
            documento_sin_plantilla,
            SUBTOTAL,
            items=[],
            summary_payload=None,
            tax_lines_payload=_lineas_fiscales(reglas),
        )
        assert total == Decimal("119.80")


def test_las_lineas_persistidas_reconstruyen_el_total_aprobado(fiscal_empresa):
    """El snapshot persistido coincide con el total: base acumulada 18 y monto 1.80."""
    application, reglas = fiscal_empresa
    with application.app_context():
        from cacao_accounting.database import SalesInvoice
        from cacao_accounting.fiscal_persistence_service import (
            calculate_document_total_with_taxes,
            load_document_fiscal_lines,
            persist_document_fiscal_snapshot,
        )

        lineas = _lineas_fiscales(reglas)
        documento = SalesInvoice(company="cacao")
        total = calculate_document_total_with_taxes(
            documento,
            SUBTOTAL,
            items=[],
            summary_payload=None,
            tax_lines_payload=lineas,
        )
        persist_document_fiscal_snapshot(
            company="cacao",
            document_type="sales_invoice",
            document_id="doc-1023",
            currency="NIO",
            tax_lines=lineas,
            tax_summary={},
            server_subtotal=SUBTOTAL,
            server_total=total,
        )
        persistidas = load_document_fiscal_lines("sales_invoice", "doc-1023")

        montos_por_concepto: dict[str, list[Decimal]] = {}
        for linea in persistidas:
            montos_por_concepto.setdefault(linea.concept, []).append(Decimal(str(linea.amount)))
        assert sorted(montos_por_concepto["TASA_FIJA"]) == [Decimal("8.0000"), Decimal("10.0000")]
        proporcional = montos_por_concepto["PROPORCIONAL"]
        assert len(proporcional) == 1
        linea_proporcional = next(
            linea_persistida for linea_persistida in persistidas if linea_persistida.concept == "PROPORCIONAL"
        )
        assert Decimal(str(linea_proporcional.base_amount)) == Decimal("18")
        assert proporcional[0] == Decimal("1.8000")

        total_reconstruible = SUBTOTAL + sum(
            Decimal(str(linea.amount))
            for linea in persistidas
            if linea.affects_document_total and not linea.included_in_price and linea.tax_type != "withholding"
        )
        assert total_reconstruible == Decimal("119.80") == total
