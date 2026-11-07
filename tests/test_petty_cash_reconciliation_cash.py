# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Conciliación de caja chica: efectivo esperado sin doble descarga.

Escenario de negocio (issue #1036): al liquidar un vale con un gasto
posteado (Dr Gasto / Cr Caja Chica), el saldo GL de la caja ya quedó
descontado; volver a sumar los gastos pendientes de reposición
duplicaba la descarga y reportaba un faltante fantasma de −100 en una
caja físicamente cuadrada. El efectivo esperado es
``ledger_balance - open_vouchers`` y el importe explicado es
``counted_cash + open_vouchers`` (invariante con el saldo GL cuando
la caja cuadra).
"""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

FECHA_CONCILIACION = date(2026, 10, 15)


@pytest.fixture
def caja_operando():
    """Aplicación con fondo de caja chica, catálogo GL y libro activo."""
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
        from cacao_accounting.database import Accounts, Book, CostCenter, Currency, Entity, Modules, PettyCashAccount, User

        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                User(id="admin", user="admin", name="Administrador", password=b"x", classification="admin", active=True),
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Book(
                    entity="cacao",
                    code="LOCAL",
                    name="Principal",
                    status="activo",
                    currency="NIO",
                    default=True,
                    is_primary=True,
                ),
                CostCenter(code="MAIN", name="Principal", entity="cacao", active=True, enabled=True),
                Accounts(
                    code="1.01.05.001",
                    name="Caja Chica Principal",
                    entity="cacao",
                    group=False,
                    active=True,
                    enabled=True,
                    account_type="petty_cash",
                ),
                Accounts(
                    code="5.01.01.001",
                    name="Gastos Operativos",
                    entity="cacao",
                    group=False,
                    active=True,
                    enabled=True,
                    account_type="expense",
                ),
            ]
        )
        database.session.commit()
        caja = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1.01.05.001")).scalar_one()
        database.session.add(
            PettyCashAccount(
                company="cacao",
                name="Fondo Principal",
                currency="NIO",
                float_amount=Decimal("1000"),
                account_id=caja.id,
            )
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _fondo_contabilizado(application, monto: Decimal) -> None:
    """Publica el fondo autorizado en el GL (forma equivalente al motor)."""
    from cacao_accounting.database import Accounts, Book, GLEntry, database

    with application.app_context():
        caja = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1.01.05.001")).scalar_one()
        libro = database.session.execute(database.select(Book).filter_by(code="LOCAL")).scalar_one()
        database.session.add(
            GLEntry(
                company="cacao",
                ledger_id=libro.id,
                account_id=caja.id,
                voucher_type="petty_cash_float",
                voucher_id="FLOAT-1036",
                posting_date=date(2026, 10, 1),
                debit=monto,
                credit=Decimal("0"),
            )
        )
        database.session.commit()


def _vale_entregado(application, monto: Decimal):
    with application.app_context():
        from cacao_accounting.bancos.services import create_petty_cash_voucher, set_petty_cash_voucher_status
        from cacao_accounting.database import PettyCashAccount, database

        fondo = database.session.execute(database.select(PettyCashAccount).filter_by(company="cacao")).scalar_one()
        vale = create_petty_cash_voucher(
            company="cacao",
            petty_cash_id=fondo.id,
            posted_date=date(2026, 10, 2),
            delivered_to="Chofer de reparto",
            concept="Gasolina de reparto",
            amount=monto,
            cost_center_code="MAIN",
        )
        vale = set_petty_cash_voucher_status(vale, "entregado")
        return vale.id


def _liquidar_vale(application, monto: Decimal, voucher_id: str) -> None:
    with application.app_context():
        from cacao_accounting.bancos.services import create_petty_cash_expense
        from cacao_accounting.database import PettyCashAccount, database

        fondo = database.session.execute(database.select(PettyCashAccount).filter_by(company="cacao")).scalar_one()
        create_petty_cash_expense(
            company="cacao",
            petty_cash_id=fondo.id,
            expense_account_code="5.01.01.001",
            concept="Liquidación de vale",
            amount=monto,
            cost_center_code="MAIN",
            posted_date=date(2026, 10, 5),
            voucher_id=voucher_id,
            actor_id="admin",
        )


def _conciliar(application, contado: Decimal) -> dict:
    with application.app_context():
        from cacao_accounting.bancos.services import create_petty_cash_reconciliation
        from cacao_accounting.database import PettyCashAccount, PettyCashReconciliation, database

        fondo = database.session.execute(database.select(PettyCashAccount).filter_by(company="cacao")).scalar_one()
        create_petty_cash_reconciliation(
            company="cacao",
            petty_cash_id=fondo.id,
            reconciliation_date=FECHA_CONCILIACION,
            counted_cash=contado,
        )
        registro = database.session.execute(database.select(PettyCashReconciliation).filter_by(company="cacao")).scalar_one()
        return {
            "ledger_balance": Decimal(str(registro.ledger_balance)),
            "open_vouchers": Decimal(str(registro.open_vouchers)),
            "expected_cash": Decimal(str(registro.expected_cash)),
            "counted_cash": Decimal(str(registro.counted_cash)),
            "explained_amount": Decimal(str(registro.explained_amount)),
            "difference": Decimal(str(registro.difference)),
        }


def test_caja_cuadrada_con_gasto_posteado_no_reporta_faltante_fantasma(caja_operando):
    """El reproducer del issue: gasto posteado y caja cuadrada ⇒ diferencia 0."""
    application = caja_operando
    _fondo_contabilizado(application, Decimal("1000"))
    voucher_id = _vale_entregado(application, Decimal("100"))
    _liquidar_vale(application, Decimal("100"), voucher_id)

    datos = _conciliar(application, Decimal("900"))

    assert datos["ledger_balance"] == Decimal("900")
    assert datos["open_vouchers"] == Decimal("0")
    assert datos["expected_cash"] == Decimal("900")
    assert datos["difference"] == Decimal("0")
    assert datos["explained_amount"] == Decimal("900")
    # El memo de reposición preserva su valor: el fondo sigue necesitando 100.
    with application.app_context():
        from cacao_accounting.bancos.services import petty_cash_pending_replenishment_total
        from cacao_accounting.database import PettyCashAccount

        fondo = database.session.execute(database.select(PettyCashAccount).filter_by(company="cacao")).scalar_one()
        assert petty_cash_pending_replenishment_total(fondo) == Decimal("100")


def test_caja_cuadrada_con_vale_abierto_sin_gl_baja_del_saldo_contable(caja_operando):
    """Vale entregado sin liquidar: expected = ledger - open_vouchers."""
    application = caja_operando
    _fondo_contabilizado(application, Decimal("1000"))
    _vale_entregado(application, Decimal("100"))

    datos = _conciliar(application, Decimal("900"))

    assert datos["ledger_balance"] == Decimal("1000")
    assert datos["open_vouchers"] == Decimal("100")
    assert datos["expected_cash"] == Decimal("900")
    assert datos["difference"] == Decimal("0")
    assert datos["explained_amount"] == Decimal("1000")


def test_un_faltante_real_se_reporta_con_el_signo_correcto(caja_operando):
    """Conteo menor al esperado guarda un faltante real de −50, no uno fantasma."""
    application = caja_operando
    _fondo_contabilizado(application, Decimal("1000"))
    _vale_entregado(application, Decimal("100"))

    datos = _conciliar(application, Decimal("850"))
    assert datos["expected_cash"] == Decimal("900")
    assert datos["difference"] == Decimal("-50")
