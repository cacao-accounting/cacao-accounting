# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1673: el comprobante importado se balancea con la tasa de cada línea."""

from __future__ import annotations

from cacao_accounting.imports.adapters.journal_entry import JournalEntryAdapter
from cacao_accounting.database import Accounts, database
import pytest


@pytest.fixture(autouse=True)
def cuentas_activas(app, entorno_contable):
    """Las pruebas de moneda usan cuentas operativas del catálogo."""
    with app.app_context():
        for cuenta in database.session.execute(
            database.select(Accounts).filter(Accounts.code.in_(["1101", "4101"]))
        ).scalars():
            cuenta.active = cuenta.enabled = True
        database.session.flush()
        yield
        database.session.rollback()


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


def test_error_interno_no_aprueba_el_comprobante(app, entorno_contable, monkeypatch):
    """Un fallo del validador contable se comunica como error del lote."""
    from cacao_accounting.contabilidad import journal_service

    def fallo(*args, **kwargs):
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(journal_service, "_validate_balanced_lines", fallo)
    with app.app_context():
        errores = JournalEntryAdapter().validate_document(_filas("3600"), {"company_id": "cacao"})
    assert any("No se pudo validar" in error for error in errores)


def _filas_sin_tasa(credito_nio: str) -> list[dict[str, str]]:
    """Comprobante multimoneda que depende de la tasa de cabecera."""
    return [
        {
            "document_ref": "AS-1673-CABECERA",
            "fecha": "2026-05-15",
            "cuenta": "1101",
            "descripcion": "Caja en dólares",
            "debito": "100",
            "credito": "0",
            "moneda": "USD",
        },
        {
            "document_ref": "AS-1673-CABECERA",
            "fecha": "2026-05-15",
            "cuenta": "4101",
            "descripcion": "Ingreso en córdobas",
            "debito": "0",
            "credito": credito_nio,
            "moneda": "NIO",
        },
    ]


def test_tasa_de_cabecera_balancea_lineas_sin_tasa_propia(app, entorno_contable):
    """La tasa del encabezado convierte la línea extranjera sin tasa explícita."""
    del entorno_contable
    with app.app_context():
        errores = JournalEntryAdapter().validate_document(
            _filas_sin_tasa("3600"),
            {"company_id": "cacao", "transaction_currency": "USD", "exchange_rate": "36"},
        )
    assert errores == []


def test_ausencia_de_tasa_no_aprueba_comprobante_multimoneda(app, entorno_contable):
    """Sin tasa de línea ni de cabecera, el comprobante no se aprueba."""
    del entorno_contable
    with app.app_context():
        errores = JournalEntryAdapter().validate_document(
            _filas_sin_tasa("3600"),
            {"company_id": "cacao"},
        )
    assert any("no esta balanceado por libro" in error for error in errores)
