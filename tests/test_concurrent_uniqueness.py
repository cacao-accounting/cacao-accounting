# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Batería de unicidad e idempotencia financiera (issue #1653).

Los flujos read-then-post de caja chica y de revaluación cambiaria no deben
duplicar reservas, reembolsos, ajustes ni reversos ante solicitudes repetidas,
reintentos fallidos o escritores concurrentes.

Primera sección: escenarios funcionales con SQLite en memoria — transiciones
de estado, idempotencia de negocio, atomicidad ante fallos y reconciliación
documento-GL. Se ejecutan en toda corrida local.

Segunda sección: concurrencia real marcada ``database`` (criterio de
aceptación del issue). Crea una base PostgreSQL propia por escenario para
intercalar dos sesiones reales sin depender del estado de otras pruebas;
se salta en motores que no son PostgreSQL.
"""

from __future__ import annotations

import atexit
import os
import tempfile
import threading
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from cacao_accounting import create_app
from cacao_accounting.bancos.services import (
    create_petty_cash_expense,
    create_petty_cash_reconciliation,
    create_petty_cash_replenishment,
    post_petty_cash_reconciliation_adjustment,
    replenish_petty_cash,
    set_petty_cash_replenishment_status,
)
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad import posting_service
from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
from cacao_accounting.database import database

COMPANY = "cacao"
MONTO = Decimal("100")


# ---------------------------------------------------------------- fixtures


def _configuracion_base() -> dict[str, Any]:
    return {
        **configuracion,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "TESTING": True,
        "MODO_ESCRITORIO": True,
    }


def _ruta_sqlite_temporal() -> str:
    """Archivo SQLite por prueba: conexiones separadas ven el estado comprometido."""
    descriptor, ruta = tempfile.mkstemp(prefix="concurrent-", suffix=".sqlite")
    os.close(descriptor)
    atexit.register(_eliminar_si_existe, ruta)
    return ruta


def _eliminar_si_existe(ruta: str) -> None:
    for sufijo in ("", "-wal", "-shm", "-journal"):
        try:
            os.unlink(ruta + sufijo)
        except FileNotFoundError:
            pass


@pytest.fixture
def caja_app():
    """App de prueba con fondo de caja chica, banco y catálogo GL mínimos."""
    application = create_app({**_configuracion_base(), "SQLALCHEMY_DATABASE_URI": f"sqlite:///{_ruta_sqlite_temporal()}"})
    with application.app_context():
        database.create_all()
        _seed_empresa(application, COMPANY)
        _seed_caja_banco(application, COMPANY)
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


@pytest.fixture
def reval_app():
    """Escenario de revaluación: banco USD con saldo GL y cuentas de diferencia."""
    application = create_app({**_configuracion_base(), "SQLALCHEMY_DATABASE_URI": f"sqlite:///{_ruta_sqlite_temporal()}"})
    with application.app_context():
        database.create_all()
        _seed_empresa(application, COMPANY)
        _seed_revaluacion(application, COMPANY)
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _seed_empresa(application, company: str) -> None:
    """Datos base: usuario, entidad, libro principal y monedas."""
    from cacao_accounting.database import Book, Currency, Entity, Modules, User

    database.session.add_all(
        [
            Modules(module="accounting", default=False, enabled=True),
            User(
                id="admin",
                user="admin",
                name="Administrador",
                password=b"x",
                classification="admin",
                active=True,
                company=company,
            ),
            Entity(
                code=company,
                name="Cacao Accounting Test",
                company_name=f"Test {company} SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            ),
            Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
            Currency(code="USD", name="Dólar", decimals=2, active=True),
        ]
    )
    database.session.commit()
    # El libro depende de la entidad: flush explicito para respetar el orden en PostgreSQL.
    database.session.add(
        Book(
            entity=company,
            code="LOCAL",
            name="Principal",
            status="activo",
            currency="NIO",
            default=True,
            is_primary=True,
        )
    )
    database.session.commit()


def _seed_caja_banco(application, company: str) -> None:
    """Catálogo GL, fondo de caja chica y cuenta bancaria operativa."""
    from cacao_accounting.database import Accounts, Bank, BankAccount, CostCenter, PettyCashAccount

    database.session.add_all(
        [
            CostCenter(code="MAIN", name="Principal", entity=company, active=True, enabled=True),
            Accounts(
                code="1.01.05.001",
                name="Caja Chica",
                entity=company,
                group=False,
                active=True,
                enabled=True,
                account_type="petty_cash",
            ),
            Accounts(
                code="5.01.01.001",
                name="Gastos Operativos",
                entity=company,
                group=False,
                active=True,
                enabled=True,
                account_type="expense",
            ),
            Accounts(
                code="1.01.02.002",
                name="Banco Principal",
                entity=company,
                group=False,
                active=True,
                enabled=True,
                account_type="bank",
            ),
        ]
    )
    database.session.commit()
    caja = database.session.execute(database.select(Accounts).filter_by(entity=company, code="1.01.05.001")).scalar_one()
    banco_gl = database.session.execute(database.select(Accounts).filter_by(entity=company, code="1.01.02.002")).scalar_one()
    database.session.add(
        PettyCashAccount(
            company=company, name="Fondo Principal", currency="NIO", float_amount=Decimal("1000"), account_id=caja.id
        )
    )
    database.session.add(Bank(name=f"Banco {company}", is_active=True))
    database.session.flush()
    banco = database.session.execute(database.select(Bank).filter_by(name=f"Banco {company}")).scalar_one()
    database.session.add(
        BankAccount(
            company=company,
            bank_id=banco.id,
            account_name="Cuenta operativa",
            account_no=f"BANK-{company}",
            gl_account_id=banco_gl.id,
            currency="NIO",
            is_active=True,
        )
    )
    database.session.commit()


def _seed_revaluacion(application, company: str) -> None:
    """Periodo abierto, tasas USD/NIO, cuentas de diferencia y saldo GL del banco."""
    from cacao_accounting.database import (
        Accounts,
        AccountingPeriod,
        Bank,
        BankAccount,
        Book,
        CompanyDefaultAccount,
        ExchangeRate,
        FiscalYear,
        GLEntry,
    )

    database.session.add_all(
        [
            Accounts(
                code="1.01.02.001",
                name="Bancos USD",
                entity=company,
                group=False,
                active=True,
                enabled=True,
                account_type="bank",
            ),
            Accounts(
                code="4.01.01.001",
                name="Ganancia cambiaria",
                entity=company,
                group=False,
                active=True,
                enabled=True,
                account_type="income",
            ),
            Accounts(
                code="5.01.02.001",
                name="Pérdida cambiaria",
                entity=company,
                group=False,
                active=True,
                enabled=True,
                account_type="expense",
            ),
        ]
    )
    database.session.commit()
    banco_usd = database.session.execute(database.select(Accounts).filter_by(entity=company, code="1.01.02.001")).scalar_one()
    ganancia = database.session.execute(database.select(Accounts).filter_by(entity=company, code="4.01.01.001")).scalar_one()
    perdida = database.session.execute(database.select(Accounts).filter_by(entity=company, code="5.01.02.001")).scalar_one()
    database.session.add(
        CompanyDefaultAccount(
            company=company,
            default_bank=banco_usd.id,
            default_expense=perdida.id,
            default_income=ganancia.id,
            unrealized_exchange_gain_account_id=ganancia.id,
            unrealized_exchange_loss_account_id=perdida.id,
        )
    )
    database.session.add(
        FiscalYear(
            id=f"FY-{company}",
            entity=company,
            name="2026",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
    )
    database.session.flush()
    database.session.add(
        AccountingPeriod(
            id=f"P-{company}-10",
            entity=company,
            fiscal_year_id=f"FY-{company}",
            name="Octubre 2026",
            start=date(2026, 10, 1),
            end=date(2026, 10, 31),
            enabled=True,
            is_closed=False,
        )
    )
    database.session.add_all(
        [
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.00"), date=date(2026, 10, 1)),
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.60"), date=date(2026, 10, 31)),
            ExchangeRate(origin="NIO", destination="USD", rate=Decimal("1") / Decimal("36.00"), date=date(2026, 10, 1)),
            ExchangeRate(origin="NIO", destination="USD", rate=Decimal("1") / Decimal("36.60"), date=date(2026, 10, 31)),
        ]
    )
    database.session.add(Bank(name=f"Banco {company}", is_active=True))
    database.session.flush()
    banco = database.session.execute(database.select(Bank).filter_by(name=f"Banco {company}")).scalar_one()
    database.session.add(
        BankAccount(
            company=company,
            bank_id=banco.id,
            account_name="Banco USD",
            account_no=f"BANK-USD-{company}",
            gl_account_id=banco_usd.id,
            currency="USD",
            is_active=True,
        )
    )
    database.session.flush()
    cuenta = database.session.execute(database.select(BankAccount).filter_by(company=company)).scalar_one()
    libro = database.session.execute(database.select(Book).filter_by(code="LOCAL")).scalar_one()
    database.session.add(
        GLEntry(
            company=company,
            ledger_id=libro.id,
            account_id=banco_usd.id,
            bank_account_id=cuenta.id,
            voucher_type="bank_transfer",
            voucher_id=f"DEPOSITO-{company}",
            posting_date=date(2026, 10, 1),
            debit=Decimal("3600"),
            credit=Decimal("0"),
            debit_in_account_currency=Decimal("100"),
            credit_in_account_currency=Decimal("0"),
            account_currency="USD",
            company_currency="NIO",
            exchange_rate=Decimal("36.00"),
        )
    )
    database.session.commit()


# ------------------------------------------------------------ utilidades


def _fondo_id(application, company: str) -> str:
    with application.app_context():
        from cacao_accounting.database import PettyCashAccount

        return database.session.execute(database.select(PettyCashAccount).filter_by(company=company)).scalar_one().id


def _banco_id(application, company: str) -> str:
    with application.app_context():
        from cacao_accounting.database import BankAccount

        return database.session.execute(database.select(BankAccount).filter_by(company=company)).scalar_one().id


def _gasto_posteado(application, company: str, monto: Decimal, dia: date) -> str:
    """Gasto posteado (genera su par GL) disponible para reposición."""
    with application.app_context():
        gasto = create_petty_cash_expense(
            company=company,
            petty_cash_id=_fondo_id(application, company),
            expense_account_code="5.01.01.001",
            concept="Gasto operativo de prueba",
            amount=monto,
            cost_center_code="MAIN",
            posted_date=dia,
            actor_id="admin",
        )
        return gasto.id


def _solicitud_aprobada(application, company: str, expense_ids: list[str], dia: date) -> str:
    """Flujo operativo completo hasta el estado aprobado."""
    with application.app_context():
        reposicion = create_petty_cash_replenishment(
            company=company,
            petty_cash_id=_fondo_id(application, company),
            expense_ids=expense_ids,
            request_date=dia,
            actor_id="admin",
        )
        reposicion = set_petty_cash_replenishment_status(reposicion, "solicitado", actor_id="admin")
        reposicion = set_petty_cash_replenishment_status(reposicion, "aprobado", actor_id="admin")
        return reposicion.id


def _nota_debito_reposicion(application, company: str, reposicion_id: str):
    with application.app_context():
        from cacao_accounting.database import GLEntry, PaymentEntry, PettyCashReplenishment

        reposicion = database.session.get(PettyCashReplenishment, reposicion_id)
        pago = database.session.get(PaymentEntry, reposicion.bank_debit_note_id)
        gl = list(
            database.session.execute(
                database.select(GLEntry).where(
                    GLEntry.voucher_type == "payment_entry",
                    GLEntry.voucher_id == pago.id,
                    GLEntry.is_cancelled.is_(False),
                )
            )
            .scalars()
            .all()
        )
        return pago, gl


def _entradas_revaluacion_activas(application, company: str) -> list:
    with application.app_context():
        from cacao_accounting.database import GLEntry

        return list(
            database.session.execute(
                database.select(GLEntry)
                .where(GLEntry.voucher_type == "exchange_revaluation")
                .where(GLEntry.is_cancelled.is_(False))
            )
            .scalars()
            .all()
        )


def _ejecutar_en_dos_hilos(trabajos: list) -> dict[str, Any]:
    """Ejecuta dos tareas en hilos con barrera de arranque simultáneo."""
    resultados: dict[str, Any] = {}
    barrera = threading.Barrier(len(trabajos))
    envolturas: list[threading.Thread] = []
    for indice, trabajo in enumerate(trabajos):
        etiqueta = f"hilo{indice}"

        def _envoltura(trabajo=trabajo, etiqueta=etiqueta):
            barrera.wait()
            try:
                resultados[etiqueta] = trabajo()
            except Exception as exc:  # noqa: BLE001 - un hilo no debe matar el test
                resultados[etiqueta] = exc

        envolturas.append(threading.Thread(target=_envoltura, name=etiqueta))
    for envoltura in envolturas:
        envoltura.start()
    for envoltura in envolturas:
        envoltura.join(120)
        assert not envoltura.is_alive(), f"{envoltura.name} quedó bloqueado"
    return resultados


def _exitos_y_errores(resultados: dict) -> tuple[int, int]:
    """Clasifica resultados de hilo en éxitos y excepciones."""
    exitos = [valor for valor in resultados.values() if not isinstance(valor, Exception)]
    errores = [valor for valor in resultados.values() if isinstance(valor, Exception)]
    return len(exitos), len(errores)


# --------------------------------------------------------- caja chica (SQLite)


def test_reembolso_duplicado_rechazado(caja_app):
    """Repetir la reposición aprobada no crea una segunda nota de débito."""
    gasto = _gasto_posteado(caja_app, COMPANY, MONTO, date(2026, 10, 5))
    reposicion_id = _solicitud_aprobada(caja_app, COMPANY, [gasto], date(2026, 10, 6))
    banco_id = _banco_id(caja_app, COMPANY)

    with caja_app.app_context():
        from cacao_accounting.database import PettyCashReplenishment

        reposicion = database.session.get(PettyCashReplenishment, reposicion_id)
        replenish_petty_cash(reposicion, bank_account_id=banco_id, actor_id="admin")

    pago, gl = _nota_debito_reposicion(caja_app, COMPANY, reposicion_id)
    assert pago.docstatus == 1
    assert pago.payment_type == "debit_note"
    assert len(gl) == 2

    with caja_app.app_context():
        from cacao_accounting.database import PettyCashReplenishment

        reposicion = database.session.get(PettyCashReplenishment, reposicion_id)
        with pytest.raises(ValueError):
            replenish_petty_cash(reposicion, bank_account_id=banco_id, actor_id="admin")

    with caja_app.app_context():
        from cacao_accounting.database import PaymentEntry

        pagos = database.session.execute(database.select(PaymentEntry).filter_by(payment_type="debit_note")).scalars().all()
        assert len(pagos) == 1


def test_reintento_tras_fallo_no_deja_nota_huerfana(caja_app, monkeypatch):
    """Fallo durante el posteo deja cero efectos; el reintento produce un único efecto."""
    gasto = _gasto_posteado(caja_app, COMPANY, MONTO, date(2026, 10, 5))
    reposicion_id = _solicitud_aprobada(caja_app, COMPANY, [gasto], date(2026, 10, 6))
    banco_id = _banco_id(caja_app, COMPANY)

    def _fallo(document, *args, **kwargs):
        raise ValueError("simulación de fallo de red durante el posteo")

    monkeypatch.setattr(posting_service, "submit_document", _fallo)
    with caja_app.app_context():
        from cacao_accounting.database import GLEntry, PaymentEntry, PettyCashReplenishment

        gl_antes = len(database.session.execute(database.select(GLEntry)).scalars().all())
        reposicion = database.session.get(PettyCashReplenishment, reposicion_id)
        with pytest.raises(ValueError):
            replenish_petty_cash(reposicion, bank_account_id=banco_id, actor_id="admin")
        assert database.session.execute(database.select(PaymentEntry)).scalars().all() == []
        assert len(database.session.execute(database.select(GLEntry)).scalars().all()) == gl_antes
        reposicion = database.session.get(PettyCashReplenishment, reposicion_id)
        assert reposicion.status == "aprobado"
        assert reposicion.bank_debit_note_id is None

    monkeypatch.undo()
    with caja_app.app_context():
        from cacao_accounting.database import PettyCashReplenishment

        reposicion = database.session.get(PettyCashReplenishment, reposicion_id)
        replenish_petty_cash(reposicion, bank_account_id=banco_id, actor_id="admin")
    pago, gl = _nota_debito_reposicion(caja_app, COMPANY, reposicion_id)
    assert pago.docstatus == 1
    assert len(gl) == 2


def test_reserva_de_gastos_no_permite_doble_solicitud(caja_app):
    """Dos solicitudes no pueden reservar el mismo gasto (una sola asignación activa)."""
    gasto = _gasto_posteado(caja_app, COMPANY, MONTO, date(2026, 10, 5))

    with caja_app.app_context():
        primera = create_petty_cash_replenishment(
            company=COMPANY,
            petty_cash_id=_fondo_id(caja_app, COMPANY),
            expense_ids=[gasto],
            request_date=date(2026, 10, 6),
            actor_id="admin",
        )
        with pytest.raises(ValueError):
            create_petty_cash_replenishment(
                company=COMPANY,
                petty_cash_id=_fondo_id(caja_app, COMPANY),
                expense_ids=[gasto],
                request_date=date(2026, 10, 6),
                actor_id="admin",
            )
        from cacao_accounting.database import PettyCashExpense

        assert database.session.get(PettyCashExpense, gasto).replenishment_id == primera.id


def test_transicion_invalida_no_avanza_reposicion(caja_app):
    """Las transiciones fuera del estado válido no mutan la reposición."""
    gasto = _gasto_posteado(caja_app, COMPANY, MONTO, date(2026, 10, 5))
    reposicion_id = _solicitud_aprobada(caja_app, COMPANY, [gasto], date(2026, 10, 6))

    with caja_app.app_context():
        from cacao_accounting.database import PettyCashReplenishment

        reposicion = database.session.get(PettyCashReplenishment, reposicion_id)
        with pytest.raises(ValueError):
            set_petty_cash_replenishment_status(reposicion, "borrador", actor_id="admin")
        assert database.session.get(PettyCashReplenishment, reposicion_id).status == "aprobado"


def test_ajuste_de_conciliacion_unico(caja_app):
    """Un ajuste por conciliación: la segunda aplicación es rechazada."""
    _gasto_posteado(caja_app, COMPANY, MONTO, date(2026, 10, 5))
    fondo_id = _fondo_id(caja_app, COMPANY)

    with caja_app.app_context():
        create_petty_cash_reconciliation(
            company=COMPANY,
            petty_cash_id=fondo_id,
            reconciliation_date=date(2026, 10, 31),
            counted_cash=Decimal("900"),
            explanation="Faltante de efectivo menor a dos.",
        )
        from cacao_accounting.bancos.services import reconcile_petty_cash
        from cacao_accounting.database import PettyCashReconciliation

        conciliacion = database.session.execute(
            database.select(PettyCashReconciliation).filter_by(company=COMPANY)
        ).scalar_one()
        assert conciliacion.difference != 0
        conciliacion = reconcile_petty_cash(conciliacion, actor_id="admin")
        diario = post_petty_cash_reconciliation_adjustment(
            conciliacion,
            adjustment_account_code="5.01.01.001",
            cost_center_code="MAIN",
            actor_id="admin",
        )
        assert diario.status == "submitted"
        with pytest.raises(ValueError) as excinfo:
            post_petty_cash_reconciliation_adjustment(
                conciliacion,
                adjustment_account_code="5.01.01.001",
                cost_center_code="MAIN",
                actor_id="admin",
            )
        assert "ya fue ajustada" in str(excinfo.value)
        assert database.session.get(PettyCashReconciliation, conciliacion.id).adjustment_journal_id == diario.id


# ------------------------------------------------------------ revaluación (SQLite)


def test_reversa_no_duplica_reversos(reval_app):
    """Repetir void no crea un segundo conjunto de reversos."""
    with reval_app.app_context():
        corrida = ExchangeRevaluationService().run(company=COMPANY, year=2026, month=10, user_id="admin")
        assert corrida.status == "posted"
        assert len(_entradas_revaluacion_activas(reval_app, COMPANY)) == 2

        ExchangeRevaluationService().void(run_id=str(corrida.id), user_id="admin", reason="primera anulación")

    assert len(_entradas_revaluacion_activas(reval_app, COMPANY)) == 2  # solo reversos activos

    with reval_app.app_context():
        with pytest.raises(Exception):
            ExchangeRevaluationService().void(run_id=str(corrida.id), user_id="admin", reason="segunda intentona")
    assert len(_entradas_revaluacion_activas(reval_app, COMPANY)) == 2


def test_doble_corrida_normaliza_a_una_corrida_activa(reval_app):
    """Reejecutar el periodo anula la corrida previa: una sola corrida activa por periodo."""
    with reval_app.app_context():
        primera = ExchangeRevaluationService().run(company=COMPANY, year=2026, month=10, user_id="admin")
        ExchangeRevaluationService().run(company=COMPANY, year=2026, month=10, user_id="admin")

        from cacao_accounting.database import ExchangeRevaluation, GLEntry

        estados = {r.status for r in database.session.execute(database.select(ExchangeRevaluation)).scalars()}
        assert estados == {"voided", "posted"}
        originales_anuladas = list(
            database.session.execute(
                database.select(GLEntry).where(
                    GLEntry.voucher_type == "exchange_revaluation",
                    GLEntry.voucher_id == str(primera.id),
                    GLEntry.is_reversal.is_(False),
                    GLEntry.is_cancelled.is_(False),
                )
            )
            .scalars()
            .all()
        )
        assert originales_anuladas == []
        # Activos totales: 2 reversos de la anulada + 2 asientos de la nueva.
        assert len(_entradas_revaluacion_activas(reval_app, COMPANY)) == 4


def test_fallo_en_posteo_revaluacion_hace_rollback_completo(reval_app, monkeypatch):
    """Excepción entre entidades y cierre: nada queda persistido (atomicidad)."""

    def _fallo(self, run, entradas, resumen, cierre, fin):
        raise RuntimeError("fallo simulado de base de datos")

    monkeypatch.setattr(ExchangeRevaluationService, "_compute_run_totals", _fallo)
    with reval_app.app_context():
        from cacao_accounting.database import ExchangeRevaluation, GLEntry

        with pytest.raises(RuntimeError):
            ExchangeRevaluationService().run(company=COMPANY, year=2026, month=10, user_id="admin")
        assert database.session.execute(database.select(ExchangeRevaluation)).scalars().all() == []
        gl_reval = list(
            database.session.execute(database.select(GLEntry).where(GLEntry.voucher_type == "exchange_revaluation"))
            .scalars()
            .all()
        )
        assert gl_reval == []


# --------------------------------------------- concurrencia real (PostgreSQL)


def _base_aislada_concurrencia():
    """Crea una base PostgreSQL propia para el escenario; salta si no hay PG."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    url = make_url(_configuracion_base()["SQLALCHEMY_DATABASE_URI"])
    if not url.drivername.startswith("postgresql"):
        pytest.skip("La concurrencia real requiere PostgreSQL en DATABASE_URL")
    nombre = f"cnc_{uuid.uuid4().hex[:10]}"
    admin_url = url.set(database="postgres")
    admin_engine = create_engine(admin_url)
    try:
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f'CREATE DATABASE "{nombre}"'))
    finally:
        admin_engine.dispose()
    return url.set(database=nombre)


def _soltar_base(url_aislada) -> None:
    """Elimina la base dedicada al finalizar el escenario."""
    from sqlalchemy import create_engine, text

    nombre = url_aislada.database
    admin_url = url_aislada.set(database="postgres")
    admin_engine = create_engine(admin_url)
    try:
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{nombre}'"))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{nombre}"'))
    finally:
        admin_engine.dispose()


@pytest.mark.database
class TestConcurrenciaPostgreSQL:
    """Escenarios de dos sesiones reales intercaladas con barrera explícita.

    Cada escenario crea su propia base PostgreSQL para no interferir con las
    demás pruebas de motor de la misma corrida de CI.
    """

    @pytest.fixture
    def pg_app_caja(self):
        url_aislada = _base_aislada_concurrencia()
        application = create_app(
            {**_configuracion_base(), "SQLALCHEMY_DATABASE_URI": url_aislada.render_as_string(hide_password=False)}
        )
        with application.app_context():
            database.create_all()
            _seed_empresa(application, COMPANY)
            _seed_caja_banco(application, COMPANY)
        yield application
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
        _soltar_base(url_aislada)

    @pytest.fixture
    def pg_app_reval(self):
        url_aislada = _base_aislada_concurrencia()
        application = create_app(
            {**_configuracion_base(), "SQLALCHEMY_DATABASE_URI": url_aislada.render_as_string(hide_password=False)}
        )
        with application.app_context():
            database.create_all()
            _seed_empresa(application, COMPANY)
            _seed_revaluacion(application, COMPANY)
        yield application
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
        _soltar_base(url_aislada)

    def test_reembolso_concurrente_un_solo_pago(self, pg_app_caja):
        """Dos reembolsos simultáneos en sesiones independientes: un solo efecto."""
        application = pg_app_caja
        from cacao_accounting.database import GLEntry, PaymentEntry

        gasto = _gasto_posteado(application, COMPANY, MONTO, date(2026, 10, 5))
        reposicion_id = _solicitud_aprobada(application, COMPANY, [gasto], date(2026, 10, 6))
        banco_id = _banco_id(application, COMPANY)

        def _reembolsar():
            with application.app_context():
                from cacao_accounting.database import PettyCashReplenishment

                reposicion = database.session.get(PettyCashReplenishment, reposicion_id)
                replenish_petty_cash(reposicion, bank_account_id=banco_id, actor_id="admin")
                return reposicion.bank_debit_note_id

        resultados = _ejecutar_en_dos_hilos([_reembolsar, _reembolsar])
        exitos, errores = _exitos_y_errores(resultados)
        assert exitos == 1, f"un solo reembolso debe tener éxito: {resultados}"
        assert errores == 1
        with application.app_context():
            from cacao_accounting.database import PettyCashReplenishment

            pagos = list(
                database.session.execute(database.select(PaymentEntry).filter_by(payment_type="debit_note")).scalars().all()
            )
            reposicion = database.session.get(PettyCashReplenishment, reposicion_id)
            assert len(pagos) == 1
            assert reposicion.bank_debit_note_id == pagos[0].id
            pares = list(
                database.session.execute(
                    database.select(GLEntry).where(
                        GLEntry.voucher_type == "payment_entry",
                        GLEntry.voucher_id == pagos[0].id,
                        GLEntry.is_cancelled.is_(False),
                    )
                )
                .scalars()
                .all()
            )
            assert len(pares) == 2

    def test_reserva_concurrente_gasto_unico(self, pg_app_caja):
        """Dos solicitudes simultáneas: exactamente una reserva del mismo gasto."""
        application = pg_app_caja
        from cacao_accounting.database import PettyCashExpense, PettyCashReplenishment

        gasto = _gasto_posteado(application, COMPANY, MONTO, date(2026, 10, 5))

        def _reservar():
            with application.app_context():
                reposicion = create_petty_cash_replenishment(
                    company=COMPANY,
                    petty_cash_id=_fondo_id(application, COMPANY),
                    expense_ids=[gasto],
                    request_date=date(2026, 10, 6),
                    actor_id="admin",
                )
                return reposicion.id

        resultados = _ejecutar_en_dos_hilos([_reservar, _reservar])
        exitos, errores = _exitos_y_errores(resultados)
        assert exitos == 1, f"un solo ganador reservando: {resultados}"
        assert errores == 1
        with application.app_context():
            ganador = min(valor for valor in resultados.values() if not isinstance(valor, Exception))
            assert database.session.get(PettyCashExpense, gasto).replenishment_id == ganador
            reposiciones = list(database.session.execute(database.select(PettyCashReplenishment)).scalars().all())
            assert len(reposiciones) == 1

    def test_anulacion_concurrente_un_solo_reverso(self, pg_app_reval):
        """void() concurrente: exactamente un conjunto de reversos y lápida permanente."""
        application = pg_app_reval
        from cacao_accounting.database import ExchangeRevaluation, GLEntry

        with application.app_context():
            corrida = ExchangeRevaluationService().run(company=COMPANY, year=2026, month=10, user_id="admin")
            corrida_id = str(corrida.id)

        def _anular():
            with application.app_context():
                ExchangeRevaluationService().void(run_id=corrida_id, user_id="admin", reason="anulación concurrente")
                return corrida_id

        resultados = _ejecutar_en_dos_hilos([_anular, _anular])
        exitos, errores = _exitos_y_errores(resultados)
        assert exitos == 1, f"una sola anulación debe triunfar: {resultados}"
        assert errores == 1
        with application.app_context():
            corrida = database.session.get(ExchangeRevaluation, corrida_id)
            assert corrida.status == "voided"
            reversos = list(
                database.session.execute(
                    database.select(GLEntry).where(
                        GLEntry.voucher_type == "exchange_revaluation",
                        GLEntry.is_reversal.is_(True),
                        GLEntry.exchange_revaluation_run_id == corrida_id,
                    )
                )
                .scalars()
                .all()
            )
            assert len(reversos) == 2
            activos = _entradas_revaluacion_activas(application, COMPANY)
            assert len(activos) == 2  # solo los reversos; los originales quedaron cancelados
            originales = list(
                database.session.execute(
                    database.select(GLEntry).where(
                        GLEntry.voucher_type == "exchange_revaluation",
                        GLEntry.voucher_id == corrida_id,
                        GLEntry.is_reversal.is_(False),
                    )
                )
                .scalars()
                .all()
            )
            assert all(entrada.is_cancelled for entrada in originales)
