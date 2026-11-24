# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1673: el comprobante importado se balancea con la tasa de cada línea."""

from __future__ import annotations

from cacao_accounting.imports.adapters.journal_entry import JournalEntryAdapter


def _filas(credito_nio: str) -> list[dict[str, str]]:
    return [
        {
            "document_ref": "AS-1673",
            "fecha": "2026-05-15",
            "cuenta": "1101",
            "descripcion": "Caja en dólares",
            "debito": "100",
            "credito": "0",
            "moneda": "USD",
            "tipo_cambio": "36",
        },
        {
            "document_ref": "AS-1673",
            "fecha": "2026-05-15",
            "cuenta": "4101",
            "descripcion": "Ingreso en córdobas",
            "debito": "0",
            "credito": credito_nio,
            "moneda": "NIO",
            "tipo_cambio": "1",
        },
    ]


def test_comprobante_balanceado_en_moneda_funcional_se_acepta(app, entorno_contable):
    """100 USD a 36 balancean 3600 NIO aunque los nominales difieran."""
    del entorno_contable
    with app.app_context():
        errores = JournalEntryAdapter().validate_document(_filas("3600"), {"company_id": "cacao"})

    assert errores == []


def test_comprobante_desbalanceado_en_moneda_funcional_se_rechaza(app, entorno_contable):
    """El motor sigue rechazando cuando los importes convertidos no coinciden."""
    del entorno_contable
    with app.app_context():
        errores = JournalEntryAdapter().validate_document(_filas("3500"), {"company_id": "cacao"})

    assert any("no esta balanceado por libro" in error for error in errores)
