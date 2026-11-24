# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1672: el prechequeo de comprobantes rechaza cuentas inexistentes o inactivas."""

from __future__ import annotations

from cacao_accounting.imports.adapters.journal_entry import JournalEntryAdapter

ERROR_CUENTA = "La cuenta 9999 no existe en la compania cacao."


def _filas(debito: str, credito: str) -> list[dict[str, str]]:
    return [
        {
            "document_ref": "AS-1672",
            "fecha": "2026-05-15",
            "cuenta": debito,
            "descripcion": "Debe",
            "debito": "100",
            "credito": "0",
            "moneda": "NIO",
        },
        {
            "document_ref": "AS-1672",
            "fecha": "2026-05-15",
            "cuenta": credito,
            "descripcion": "Haber",
            "debito": "0",
            "credito": "100",
            "moneda": "NIO",
        },
    ]


def test_cuenta_inexistente_se_rechaza_en_la_importacion(app, entorno_contable):
    """Un comprobante balanceado con códigos desconocidos no pasa el prechequeo."""
    del entorno_contable
    with app.app_context():
        errores = JournalEntryAdapter().validate_document(_filas("9999", "8888"), {"company_id": "cacao"})

    assert errores == [ERROR_CUENTA]


def test_cuentas_existentes_siguen_aceptandose(app, entorno_contable):
    """Los códigos válidos del catálogo mantienen el flujo sin cambios."""
    del entorno_contable
    with app.app_context():
        errores = JournalEntryAdapter().validate_document(_filas("1101", "4101"), {"company_id": "cacao"})

    assert errores == []
