# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Saldo GL de caja chica en instalaciones multi-libro.

Escenario de negocio (issue #1035): el motor contable publica una fila
``GLEntry`` por cada libro activo; el balance de caja chica debe leerse
del libro activo principal, igual que los demás consultados de banca
(``_compute_gl_balance``), y excluir los pares de anulación del mismo
período. Sumar todos los libros multiplica el saldo por N y genera
diferencias falsas de conciliación contra el efectivo contado.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

CUENTA_CAJA = "1.01.05.001"


@pytest.fixture
def caja_chica_multilibro():
    """Compañía con dos libros activos y un fondo de caja chica."""
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
        from cacao_accounting.database import Accounts, Book, Currency, Entity, PettyCashAccount

        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao Accounting",
                company_name="Cacao Accounting SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        database.session.add_all(
            [
                Book(
                    entity="cacao",
                    code="LOCAL",
                    name="Principal",
                    status="activo",
                    currency="NIO",
                    default=True,
                    is_primary=True,
                ),
                Book(entity="cacao", code="AUX", name="Libro Auxiliar", status="activo", currency="NIO"),
                Accounts(code=CUENTA_CAJA, name="Caja Chica Principal", entity="cacao", type_="asset"),
            ]
        )
        database.session.commit()
        cuenta = database.session.execute(database.select(Accounts).filter_by(code=CUENTA_CAJA)).scalar_one()
        database.session.add(
            PettyCashAccount(
                company="cacao",
                account_id=cuenta.id,
                name="Fondo Principal",
                currency="NIO",
                float_amount=1000,
            )
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _asiento_gl(
    application,
    *,
    ledger_code: str,
    debit: Decimal = Decimal("0"),
    credit: Decimal = Decimal("0"),
    voucher: str = "PC-2026-001",
    posting_date: date | None = None,
    is_cancelled: bool = False,
    is_reversal: bool = False,
) -> Any:
    """Publicado de un asiento de caja chica en un libro (forma del motor)."""
    from cacao_accounting.database import Accounts, Book, GLEntry, database

    with application.app_context():
        cuenta = database.session.execute(database.select(Accounts).filter_by(code=CUENTA_CAJA)).scalar_one()
        libro = database.session.execute(database.select(Book).filter_by(entity="cacao", code=ledger_code)).scalar_one()
        asiento = GLEntry(
            company="cacao",
            ledger_id=libro.id,
            account_id=cuenta.id,
            voucher_type="petty_cash",
            voucher_id=voucher,
            posting_date=posting_date or date(2026, 10, 1),
            debit=debit,
            credit=credit,
            is_cancelled=is_cancelled,
            is_reversal=is_reversal,
        )
        database.session.add(asiento)
        database.session.commit()
        return asiento.id


def _saldo_de_fondo(application) -> Decimal:
    with application.app_context():
        from cacao_accounting.bancos.services import petty_cash_ledger_balance
        from cacao_accounting.database import PettyCashAccount

        fondo = database.session.execute(database.select(PettyCashAccount)).scalar_one()
        return petty_cash_ledger_balance(fondo)


def test_el_saldo_del_fondo_lee_el_libro_principal_y_no_consolida_todo(caja_chica_multilibro):
    """El reproducer del issue: fondo 1000 y gasto 100 en 2 libros → saldo 900."""
    application = caja_chica_multilibro
    # Acomodo (posting) tal como escribe el motor: una fila por каждый libro activo.
    _asiento_gl(application, ledger_code="LOCAL", debit=Decimal("1000"))
    _asiento_gl(application, ledger_code="AUX", debit=Decimal("1000"))
    _asiento_gl(application, ledger_code="LOCAL", credit=Decimal("100"))
    _asiento_gl(application, ledger_code="AUX", credit=Decimal("100"))
    assert _saldo_de_fondo(application) == Decimal("900")


def test_el_saldo_excluye_los_pares_de_anulación_del_mismo_período(caja_chica_multilibro):
    """La política append-only: las anulaciones no alteran el saldo operativo.

    Reposición de 500 publicada y anulada (par original anulado + reversa
    en el mismo período): ambos movimientos salen del saldo operativo y
    este queda en el fondo autorizado, sin depresión ni sobregiro ficticio.
    """
    application = caja_chica_multilibro
    _asiento_gl(application, ledger_code="LOCAL", debit=Decimal("1000"))
    _asiento_gl(application, ledger_code="AUX", debit=Decimal("1000"))
    _asiento_gl(
        application,
        ledger_code="LOCAL",
        debit=Decimal("500"),
        voucher="PC-2026-REPOSICION",
        is_cancelled=True,
    )
    _asiento_gl(
        application,
        ledger_code="LOCAL",
        credit=Decimal("500"),
        voucher="PC-2026-REPOSICION",
        is_reversal=True,
    )
    _asiento_gl(
        application,
        ledger_code="AUX",
        debit=Decimal("500"),
        voucher="PC-2026-REPOSICION",
        is_cancelled=True,
    )
    _asiento_gl(
        application,
        ledger_code="AUX",
        credit=Decimal("500"),
        voucher="PC-2026-REPOSICION",
        is_reversal=True,
    )
    assert _saldo_de_fondo(application) == Decimal("1000")


def test_la_consulta_con_fecha_de_corte_excluye_movimientos_posteriores(caja_chica_multilibro):
    """La consistencia histórica de conciliaciones exige corte de fecha."""
    application = caja_chica_multilibro
    _asiento_gl(application, ledger_code="LOCAL", debit=Decimal("1000"))
    _asiento_gl(
        application,
        ledger_code="LOCAL",
        credit=Decimal("250"),
        posting_date=date(2026, 10, 1) + timedelta(days=3),
    )
    with application.app_context():
        from cacao_accounting.bancos.services import petty_cash_ledger_balance
        from cacao_accounting.database import PettyCashAccount

        fondo = database.session.execute(database.select(PettyCashAccount)).scalar_one()
        assert petty_cash_ledger_balance(fondo, as_of_date=date(2026, 10, 1)) == Decimal("1000")
        assert petty_cash_ledger_balance(fondo) == Decimal("750")
