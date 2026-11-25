# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1607: el dashboard separa saldo de cuenta y total en moneda base."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.api.dashboard import get_banks_data
from cacao_accounting.config import configuracion
from cacao_accounting.database import Accounts, Bank, BankAccount, Book, Currency, Entity, GLEntry, database


@pytest.fixture
def bank_balance_scene():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dólar", decimals=2, active=True, default=False),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J-1607",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        libro = Book(
            entity="cacao",
            code="DEFAULT_BOOK",
            name="Libro principal",
            status="activo",
            is_primary=True,
            default=True,
            currency="NIO",
        )
        database.session.add(libro)
        database.session.flush()
        banco = Bank(name="Banco 1607", is_active=True)
        database.session.add(banco)
        database.session.flush()
        cuenta = Accounts(
            entity="cacao",
            code="1102",
            name="Banco USD",
            classification="activo",
            group=False,
        )
        database.session.add(cuenta)
        database.session.flush()
        cuenta_bancaria = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta USD",
            account_no="USD-1607",
            currency="USD",
            gl_account_id=cuenta.id,
            is_active=True,
        )
        database.session.add(cuenta_bancaria)
        database.session.flush()
        database.session.add(
            GLEntry(
                posting_date=date(2026, 5, 15),
                company="cacao",
                account_id=cuenta.id,
                ledger_id=libro.id,
                debit=Decimal("3600"),
                credit=Decimal("0"),
                debit_in_account_currency=Decimal("100"),
                credit_in_account_currency=Decimal("0"),
                account_currency="USD",
                company_currency="NIO",
                exchange_rate=Decimal("36"),
                voucher_type="journal_entry",
                voucher_id="JE-1607",
                is_cancelled=False,
            )
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_saldo_de_cuenta_usa_su_moneda_y_total_usa_moneda_base(bank_balance_scene):
    """La tabla muestra 100 USD y el KPI 3,600 NIO, no 3,600 USD."""
    with bank_balance_scene.app_context():
        payload = get_banks_data("cacao", "NIO", None, None)

    fila = payload["tables"]["account_balances"][0]
    assert Decimal(str(fila["balance"])) == Decimal("100")
    assert fila["currency"] == "USD"

    kpi = payload["kpis"]["balance"]
    assert Decimal(str(kpi["value"])) == Decimal("3600")
    assert kpi["currency"] == "NIO"


def test_segunda_cuenta_en_otra_moneda_conserva_su_propio_saldo(bank_balance_scene):
    """#1597: una cuenta EUR muestra 100 EUR sin alterar el total base."""
    with bank_balance_scene.app_context():
        database.session.add(Currency(code="EUR", name="Euro", decimals=2, active=True, default=False))
        banco = Bank(name="Banco EUR", is_active=True)
        database.session.add(banco)
        database.session.flush()
        cuenta = Accounts(
            entity="cacao",
            code="1103",
            name="Banco EUR",
            classification="activo",
            group=False,
        )
        database.session.add(cuenta)
        database.session.flush()
        libro = database.session.query(Book).filter_by(entity="cacao").first()
        database.session.add(
            BankAccount(
                company="cacao",
                bank_id=banco.id,
                account_name="Cuenta EUR",
                account_no="EUR-1597",
                currency="EUR",
                gl_account_id=cuenta.id,
                is_active=True,
            )
        )
        database.session.add(
            GLEntry(
                posting_date=date(2026, 5, 16),
                company="cacao",
                account_id=cuenta.id,
                ledger_id=libro.id,
                debit=Decimal("3400"),
                credit=Decimal("0"),
                debit_in_account_currency=Decimal("100"),
                credit_in_account_currency=Decimal("0"),
                account_currency="EUR",
                company_currency="NIO",
                exchange_rate=Decimal("34"),
                voucher_type="journal_entry",
                voucher_id="JE-1597",
                is_cancelled=False,
            )
        )
        database.session.commit()

        payload = get_banks_data("cacao", "NIO", None, None)

    filas = {fila["account_no"]: fila for fila in payload["tables"]["account_balances"]}
    assert Decimal(str(filas["EUR-1597"]["balance"])) == Decimal("100")
    assert filas["EUR-1597"]["currency"] == "EUR"
    assert Decimal(str(filas["USD-1607"]["balance"])) == Decimal("100")
    assert Decimal(str(payload["kpis"]["balance"]["value"])) == Decimal("7000")


def test_cuentas_comparten_gl_con_moneda_distinta(bank_balance_scene):
    """#2262: cada banco ve solo el saldo de su moneda aunque comparta cuenta GL."""
    with bank_balance_scene.app_context():
        cuenta = database.session.query(Accounts).filter_by(entity="cacao", code="1102").first()
        libro = database.session.query(Book).filter_by(entity="cacao").first()
        database.session.add(Currency(code="EUR", name="Euro", decimals=2, active=True, default=False))
        banco = Bank(name="Banco compartido", is_active=True)
        database.session.add(banco)
        database.session.flush()
        cuenta_eur = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta EUR compartida",
            account_no="EUR-2262",
            currency="EUR",
            gl_account_id=cuenta.id,
            is_active=True,
        )
        database.session.add(cuenta_eur)
        database.session.flush()
        database.session.add(
            GLEntry(
                posting_date=date(2026, 5, 17),
                company="cacao",
                account_id=cuenta.id,
                bank_account_id=cuenta_eur.id,
                ledger_id=libro.id,
                debit=Decimal("1700"),
                credit=Decimal("0"),
                debit_in_account_currency=Decimal("50"),
                credit_in_account_currency=Decimal("0"),
                account_currency="EUR",
                company_currency="NIO",
                exchange_rate=Decimal("34"),
                voucher_type="journal_entry",
                voucher_id="JE-2262",
                is_cancelled=False,
            )
        )
        database.session.commit()

        payload = get_banks_data("cacao", "NIO", None, None)

    filas = {fila["account_no"]: fila for fila in payload["tables"]["account_balances"]}
    assert Decimal(str(filas["USD-1607"]["balance"])) == Decimal("100")
    assert filas["USD-1607"]["currency"] == "USD"
    assert Decimal(str(filas["EUR-2262"]["balance"])) == Decimal("50")
    assert filas["EUR-2262"]["currency"] == "EUR"
    assert Decimal(str(payload["kpis"]["balance"]["value"])) == Decimal("5300")


def test_cuentas_comparten_gl_y_moneda_sin_duplicar_saldo(bank_balance_scene):
    """#2262: dos cuentas de la misma moneda y GL muestran su saldo identificado."""
    with bank_balance_scene.app_context():
        libro = database.session.query(Book).filter_by(entity="cacao").first()
        compartida = Accounts(
            entity="cacao",
            code="1104",
            name="Banco compartido",
            classification="activo",
            group=False,
        )
        database.session.add(compartida)
        database.session.flush()
        banco_a = Bank(name="Banco USD A", is_active=True)
        banco_b = Bank(name="Banco USD B", is_active=True)
        database.session.add_all([banco_a, banco_b])
        database.session.flush()
        cuenta_a = BankAccount(
            company="cacao",
            bank_id=banco_a.id,
            account_name="Cuenta USD A",
            account_no="USD-A-2262",
            currency="USD",
            gl_account_id=compartida.id,
            is_active=True,
        )
        cuenta_b = BankAccount(
            company="cacao",
            bank_id=banco_b.id,
            account_name="Cuenta USD B",
            account_no="USD-B-2262",
            currency="USD",
            gl_account_id=compartida.id,
            is_active=True,
        )
        database.session.add_all([cuenta_a, cuenta_b])
        database.session.flush()
        for cuenta_bancaria, importe, monto_base, voucher in (
            (cuenta_a, "100", "3600", "JE-2262-A"),
            (cuenta_b, "50", "1800", "JE-2262-B"),
        ):
            database.session.add(
                GLEntry(
                    posting_date=date(2026, 5, 18),
                    company="cacao",
                    account_id=compartida.id,
                    bank_account_id=cuenta_bancaria.id,
                    ledger_id=libro.id,
                    debit=Decimal(monto_base),
                    credit=Decimal("0"),
                    debit_in_account_currency=Decimal(importe),
                    credit_in_account_currency=Decimal("0"),
                    account_currency="USD",
                    company_currency="NIO",
                    exchange_rate=Decimal("36"),
                    voucher_type="journal_entry",
                    voucher_id=voucher,
                    is_cancelled=False,
                )
            )
        database.session.commit()

        payload = get_banks_data("cacao", "NIO", None, None)

    filas = {fila["account_no"]: fila for fila in payload["tables"]["account_balances"]}
    assert Decimal(str(filas["USD-A-2262"]["balance"])) == Decimal("100")
    assert Decimal(str(filas["USD-B-2262"]["balance"])) == Decimal("50")
    assert Decimal(str(payload["kpis"]["balance"]["value"])) == Decimal("9000")


def test_movimientos_legacy_ambiguos_no_se_atribuyen(bank_balance_scene):
    """#2262: sin identidad bancaria, un GL compartido no asigna el saldo a ambos."""
    with bank_balance_scene.app_context():
        cuenta = database.session.query(Accounts).filter_by(entity="cacao", code="1102").first()
        libro = database.session.query(Book).filter_by(entity="cacao").first()
        banco = Bank(name="Banco USD dos", is_active=True)
        database.session.add(banco)
        database.session.flush()
        database.session.add(
            BankAccount(
                company="cacao",
                bank_id=banco.id,
                account_name="Cuenta USD dos",
                account_no="USD2-2262",
                currency="USD",
                gl_account_id=cuenta.id,
                is_active=True,
            )
        )
        database.session.add(
            GLEntry(
                posting_date=date(2026, 5, 18),
                company="cacao",
                account_id=cuenta.id,
                ledger_id=libro.id,
                debit=Decimal("1800"),
                credit=Decimal("0"),
                debit_in_account_currency=Decimal("50"),
                credit_in_account_currency=Decimal("0"),
                account_currency="USD",
                company_currency="NIO",
                exchange_rate=Decimal("36"),
                voucher_type="journal_entry",
                voucher_id="JE-2262-C",
                is_cancelled=False,
            )
        )
        database.session.commit()

        payload = get_banks_data("cacao", "NIO", None, None)

    filas = {fila["account_no"]: fila for fila in payload["tables"]["account_balances"]}
    assert Decimal(str(filas["USD-1607"]["balance"])) == Decimal("0")
    assert Decimal(str(filas["USD2-2262"]["balance"])) == Decimal("0")
    assert Decimal(str(payload["kpis"]["balance"]["value"])) == Decimal("5400")


def test_total_kpi_usa_la_moneda_del_libro_primario(bank_balance_scene):
    """#2262: el total se etiqueta con la moneda del libro que suma, no con la solicitada."""
    with bank_balance_scene.app_context():
        database.session.add(
            Entity(
                code="cacaousd",
                name="Cacao USD",
                company_name="Cacao USD SA",
                tax_id="J-2262-USD",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        libro = Book(
            entity="cacaousd",
            code="USD_BOOK",
            name="Libro USD",
            status="activo",
            is_primary=True,
            default=True,
            currency="USD",
        )
        database.session.add(libro)
        database.session.flush()
        banco = Bank(name="Banco USD contable", is_active=True)
        database.session.add(banco)
        database.session.flush()
        cuenta = Accounts(
            entity="cacaousd",
            code="1102",
            name="Banco contable USD",
            classification="activo",
            group=False,
        )
        database.session.add(cuenta)
        database.session.flush()
        cuenta_bancaria = BankAccount(
            company="cacaousd",
            bank_id=banco.id,
            account_name="Cuenta contable USD",
            account_no="USD-2262-KPI",
            currency="USD",
            gl_account_id=cuenta.id,
            is_active=True,
        )
        database.session.add(cuenta_bancaria)
        database.session.flush()
        database.session.add(
            GLEntry(
                posting_date=date(2026, 5, 19),
                company="cacaousd",
                account_id=cuenta.id,
                bank_account_id=cuenta_bancaria.id,
                ledger_id=libro.id,
                debit=Decimal("100"),
                credit=Decimal("0"),
                debit_in_account_currency=Decimal("100"),
                credit_in_account_currency=Decimal("0"),
                account_currency="USD",
                company_currency="USD",
                exchange_rate=Decimal("1"),
                voucher_type="journal_entry",
                voucher_id="JE-2262-KPI",
                is_cancelled=False,
            )
        )
        database.session.commit()

        payload = get_banks_data("cacaousd", "NIO", None, None)

    fila = payload["tables"]["account_balances"][0]
    assert Decimal(str(fila["balance"])) == Decimal("100")
    assert fila["currency"] == "USD"
    kpi = payload["kpis"]["balance"]
    assert Decimal(str(kpi["value"])) == Decimal("100")
    assert kpi["currency"] == "USD"


def test_suma_partidas_identificadas_y_legacy_de_gl_unico(bank_balance_scene):
    """#2262: con una sola cuenta en el GL, el saldo suma directas y legacy."""
    with bank_balance_scene.app_context():
        libro = database.session.query(Book).filter_by(entity="cacao").first()
        cuenta = Accounts(entity="cacao", code="1105", name="Banco mixto", classification="activo", group=False)
        database.session.add(cuenta)
        database.session.flush()
        banco = Bank(name="Banco mixto", is_active=True)
        database.session.add(banco)
        database.session.flush()
        cuenta_bancaria = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta mixta",
            account_no="USD-MIX-2262",
            currency="USD",
            gl_account_id=cuenta.id,
            is_active=True,
        )
        database.session.add(cuenta_bancaria)
        database.session.flush()
        for monto, monto_base, banco_id, voucher in (
            ("100", "3600", cuenta_bancaria.id, "JE-2262-MIX-DIRECT"),
            ("50", "1800", None, "JE-2262-MIX-LEGACY"),
        ):
            database.session.add(
                GLEntry(
                    posting_date=date(2026, 5, 20),
                    company="cacao",
                    account_id=cuenta.id,
                    bank_account_id=banco_id,
                    ledger_id=libro.id,
                    debit=Decimal(monto_base),
                    credit=Decimal("0"),
                    debit_in_account_currency=Decimal(monto),
                    credit_in_account_currency=Decimal("0"),
                    account_currency="USD",
                    company_currency="NIO",
                    exchange_rate=Decimal("36"),
                    voucher_type="journal_entry",
                    voucher_id=voucher,
                    is_cancelled=False,
                )
            )
        database.session.commit()

        payload = get_banks_data("cacao", "NIO", None, None)

    fila = next(fila for fila in payload["tables"]["account_balances"] if fila["account_no"] == "USD-MIX-2262")
    assert Decimal(str(fila["balance"])) == Decimal("150")
    assert Decimal(str(payload["kpis"]["balance"]["value"])) == Decimal("9000")


def test_transferencia_entre_cuentas_con_gl_compartido_conserva_saldos(bank_balance_scene):
    """#2262: una transferencia entre dos cuentas del mismo GL no netea ambas filas."""
    with bank_balance_scene.app_context():
        libro = database.session.query(Book).filter_by(entity="cacao").first()
        compartida = Accounts(entity="cacao", code="1106", name="Banco transferencias", classification="activo", group=False)
        database.session.add(compartida)
        database.session.flush()
        cuentas = []
        for sufijo in ("A", "B"):
            banco = Bank(name=f"Banco transferencia {sufijo}", is_active=True)
            database.session.add(banco)
            database.session.flush()
            cuenta = BankAccount(
                company="cacao",
                bank_id=banco.id,
                account_name=f"Cuenta transferencia {sufijo}",
                account_no=f"USD-TR-{sufijo}-2262",
                currency="USD",
                gl_account_id=compartida.id,
                is_active=True,
            )
            database.session.add(cuenta)
            database.session.flush()
            cuentas.append(cuenta)
        movimientos = (
            (cuentas[0], "100", "3600", "0", "0", "JE-2262-TR-A"),
            (cuentas[1], "50", "1800", "0", "0", "JE-2262-TR-B"),
            (cuentas[0], "0", "0", "30", "1080", "JE-2262-TR-OUT"),
            (cuentas[1], "30", "1080", "0", "0", "JE-2262-TR-IN"),
        )
        for cuenta_bancaria, debito, debito_base, credito, credito_base, voucher in movimientos:
            database.session.add(
                GLEntry(
                    posting_date=date(2026, 5, 21),
                    company="cacao",
                    account_id=compartida.id,
                    bank_account_id=cuenta_bancaria.id,
                    ledger_id=libro.id,
                    debit=Decimal(debito_base),
                    credit=Decimal(credito_base),
                    debit_in_account_currency=Decimal(debito),
                    credit_in_account_currency=Decimal(credito),
                    account_currency="USD",
                    company_currency="NIO",
                    exchange_rate=Decimal("36"),
                    voucher_type="journal_entry",
                    voucher_id=voucher,
                    is_cancelled=False,
                )
            )
        database.session.commit()

        payload = get_banks_data("cacao", "NIO", None, None)

    filas = {fila["account_no"]: fila for fila in payload["tables"]["account_balances"]}
    assert Decimal(str(filas["USD-TR-A-2262"]["balance"])) == Decimal("70")
    assert Decimal(str(filas["USD-TR-B-2262"]["balance"])) == Decimal("80")
    assert Decimal(str(payload["kpis"]["balance"]["value"])) == Decimal("9000")


def test_saldo_ignora_cancelados_y_libro_secundario(bank_balance_scene):
    """#2262: el saldo excluye asientos cancelados y libros no primarios."""
    with bank_balance_scene.app_context():
        libro = database.session.query(Book).filter_by(entity="cacao").first()
        secundario = Book(
            entity="cacao",
            code="ALT_BOOK",
            name="Libro alterno",
            status="activo",
            is_primary=False,
            default=False,
            currency="NIO",
        )
        database.session.add(secundario)
        database.session.flush()
        cuenta = Accounts(entity="cacao", code="1107", name="Banco alcance", classification="activo", group=False)
        database.session.add(cuenta)
        database.session.flush()
        banco = Bank(name="Banco alcance", is_active=True)
        database.session.add(banco)
        database.session.flush()
        cuenta_bancaria = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta alcance",
            account_no="USD-SCOPE-2262",
            currency="USD",
            gl_account_id=cuenta.id,
            is_active=True,
        )
        database.session.add(cuenta_bancaria)
        database.session.flush()
        for monto, monto_base, ledger, cancelado, voucher in (
            ("100", "3600", libro.id, False, "JE-2262-SCOPE"),
            ("50", "1800", libro.id, True, "JE-2262-CANCELLED"),
            ("200", "7200", secundario.id, False, "JE-2262-SECONDARY"),
        ):
            database.session.add(
                GLEntry(
                    posting_date=date(2026, 5, 22),
                    company="cacao",
                    account_id=cuenta.id,
                    bank_account_id=cuenta_bancaria.id,
                    ledger_id=ledger,
                    debit=Decimal(monto_base),
                    credit=Decimal("0"),
                    debit_in_account_currency=Decimal(monto),
                    credit_in_account_currency=Decimal("0"),
                    account_currency="USD",
                    company_currency="NIO",
                    exchange_rate=Decimal("36"),
                    voucher_type="journal_entry",
                    voucher_id=voucher,
                    is_cancelled=cancelado,
                )
            )
        database.session.commit()

        payload = get_banks_data("cacao", "NIO", None, None)

    fila = next(fila for fila in payload["tables"]["account_balances"] if fila["account_no"] == "USD-SCOPE-2262")
    assert Decimal(str(fila["balance"])) == Decimal("100")
    assert Decimal(str(payload["kpis"]["balance"]["value"])) == Decimal("7200")
