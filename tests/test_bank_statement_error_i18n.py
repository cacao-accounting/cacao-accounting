# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2267: los errores visibles del adaptador de extractos bancarios se traducen."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from flask_babel import force_locale
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Bank, BankAccount, Currency, Entity, database
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter


@pytest.fixture(name="extracto_2267")
def extracto_2267_fixture():
    """Prepara dos compañías con cuenta bancaria para validar errores visibles."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:8].upper()
    company_code = f"C{suffix}"
    other_company = f"O{suffix}"
    with app.app_context():
        database.create_all()
        currency = Currency(code=f"M{suffix}", name="Moneda 2267", decimals=4, active=True, default=False)
        companies = [
            Entity(
                code=code,
                name=f"Compañía {code}",
                company_name=f"Compañía {code} SA",
                tax_id=f"T{code}",
                currency=currency.code,
                enabled=True,
                status="activo",
            )
            for code in (company_code, other_company)
        ]
        database.session.add_all([currency, *companies])
        database.session.flush()
        bank = Bank(name=f"Banco {suffix}")
        database.session.add(bank)
        database.session.flush()
        account = BankAccount(
            company=other_company,
            bank_id=bank.id,
            account_name=f"Cuenta {suffix}",
            account_no=f"ACC-{suffix}",
            currency=currency.code,
            is_active=True,
        )
        database.session.add(account)
        database.session.commit()
        identifiers = {"company": company_code, "account": account.id}

    yield app, identifiers

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _fila(identifiers: dict, deposit=None) -> dict:
    """Construye una fila con valores modificables por la prueba."""
    return {
        "bank_account_id": identifiers["account"],
        "posting_date": date(2026, 5, 15),
        "reference_number": "REF-2267",
        "description": "Prueba de traducción",
        "deposit": deposit,
        "withdrawal": None,
    }


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        ("es", ["Monto bancario inválido en columna 'deposit'", "12.345"]),
        ("en", ["Invalid bank amount in column 'deposit'", "12.345"]),
    ],
)
def test_error_de_precision_incluye_campo_y_valor(extracto_2267, locale, expected):
    """El error de precisión conserva el campo, el valor y el detalle traducidos."""
    app, identifiers = extracto_2267
    with app.app_context(), force_locale(locale):
        errores = BankStatementAdapter().validate_row(_fila(identifiers, "12.345"))

    assert any(all(fragment in error for fragment in expected) for error in errores)


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        ("es", "El monto bancario en columna 'deposit' no puede ser negativo."),
        ("en", "The bank amount in column 'deposit' cannot be negative."),
    ],
)
def test_error_de_monto_negativo_se_traduce(extracto_2267, locale, expected):
    """El error de monto negativo identifica la columna en ambos idiomas."""
    app, identifiers = extracto_2267
    with app.app_context(), force_locale(locale):
        errores = BankStatementAdapter().validate_row(_fila(identifiers, "-5"))

    assert expected in errores


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        ("es", "La fila bancaria debe contener un depósito o un retiro mayor que cero."),
        ("en", "The bank row must contain a deposit or a withdrawal greater than zero."),
    ],
)
def test_error_de_fila_vacia_se_traduce(extracto_2267, locale, expected):
    """Una fila sin importes informa la regla en el idioma activo."""
    app, identifiers = extracto_2267
    with app.app_context(), force_locale(locale):
        errores = BankStatementAdapter().validate_row(_fila(identifiers))

    assert expected in errores


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        ("es", "pertenece a la compañía"),
        ("en", "belongs to company"),
    ],
)
def test_error_de_compania_en_documento_se_traduce(extracto_2267, locale, expected):
    """La validación de compañía del documento usa catálogo y parámetros nombrados."""
    app, identifiers = extracto_2267
    with app.app_context(), force_locale(locale):
        errores = BankStatementAdapter().validate_document([_fila(identifiers, "100")], {"company_id": identifiers["company"]})

    assert any(expected in error for error in errores)
    assert any(identifiers["account"] in error for error in errores)


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        ("es", "El periodo contable para la fecha 2026-05-15 está cerrado o no existe."),
        ("en", "The accounting period for date 2026-05-15 is closed or does not exist."),
    ],
)
def test_error_de_periodo_cerrado_se_traduce(extracto_2267, locale, expected):
    """La validación de período del documento conserva la fecha y usa el catálogo."""
    app, identifiers = extracto_2267
    with app.app_context(), force_locale(locale):
        errores = BankStatementAdapter().validate_document([_fila(identifiers, "100")], {"company_id": identifiers["company"]})

    assert any(expected in error for error in errores)
