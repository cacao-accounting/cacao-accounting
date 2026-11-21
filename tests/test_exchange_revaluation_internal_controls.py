# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""El alta de revaluaciones cambiarias convive con los controles internos (#2119).

Escenario de negocio: con ``INTERNAL_CONTROLS_ENFORCE`` activo, el identificador
documental de la corrida se asigna mientras la corrida aún es borrador, antes de
marcarla como posteada. Así el alta no choca con el guard de inmutabilidad de
datos financieros posteados y la corrida válida se crea y contabiliza
normalmente, con ``docstatus`` final 1 y ``document_no`` asignado.
"""

from __future__ import annotations

import calendar
import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.exchange_revaluation_service import ExchangeRevaluationService
from cacao_accounting.database import (
    Accounts,
    AccountingPeriod,
    Bank,
    BankAccount,
    Book,
    CompanyDefaultAccount,
    Currency,
    Entity,
    ExchangeRate,
    ExchangeRevaluation,
    FiscalYear,
    GLEntry,
    Modules,
    User,
    database,
)

pytestmark = pytest.mark.database


def _obtener_o_crear_moneda(code: str, name: str, decimals: int = 2, active: bool = True, default: bool = False):
    moneda = database.session.execute(database.select(Currency).filter_by(code=code)).scalar_one_or_none()
    if moneda is None:
        moneda = Currency(code=code, name=name, decimals=decimals, active=active, default=default)
        database.session.add(moneda)
    elif default and not getattr(moneda, "default", False):
        moneda.default = True
    return moneda


@pytest.fixture
def business_app(tmp_path):
    """Aplicación con los controles internos de integridad financiera activos."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'business.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base de pruebas dedicada.")
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "MODO_ESCRITORIO": False,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )
    with application.app_context():
        database.create_all()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _mes_de_cierre_libre() -> tuple[int, int]:
    """Elige un mes de cierre sin tasas USD<->NIO ya registradas en esa fecha."""
    ocupadas = database.session.execute(
        database.select(ExchangeRate.origin, ExchangeRate.destination, ExchangeRate.date).where(
            ExchangeRate.origin.in_(["USD", "NIO"]), ExchangeRate.destination.in_(["USD", "NIO"])
        )
    ).all()
    for anio in range(2001, 2027):
        for mes in range(2, 12):
            cierre = date(anio, mes, calendar.monthrange(anio, mes)[1])
            if not any(tasa_fecha == cierre for _origen, _destino, tasa_fecha in ocupadas):
                return anio, mes
    raise AssertionError("No hay mes libre para sembrar el escenario de tasas.")


def _sembrar_exposicion_bancaria(company: str) -> str:
    """Compañía con banco en USD, libro NIO y tasa de cierre; devuelve el período."""
    anio, mes = _mes_de_cierre_libre()
    inicio = date(anio, mes, 1)
    cierre = date(anio, mes, calendar.monthrange(anio, mes)[1])
    _obtener_o_crear_moneda("NIO", "Córdoba", 2, True, True)
    _obtener_o_crear_moneda("USD", "Dólar", 2, True, False)
    if database.session.execute(database.select(Modules).filter_by(module="accounting")).scalar_one_or_none() is None:
        database.session.add(Modules(module="accounting", default=False, enabled=True))
    if database.session.execute(database.select(Entity).filter_by(code=company)).scalar_one_or_none() is None:
        database.session.add(
            Entity(
                code=company,
                name=f"Empresa de prueba {company}",
                company_name=f"Empresa de prueba {company} SA",
                tax_id=f"TAX-{company}",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
    database.session.flush()
    database.session.add(
        User(
            user=f"qa-{company}",
            name="Responsable de contabilidad",
            password=b"business-test",
            classification="admin",
            active=True,
            company=company,
        )
    )
    ledger = Book(
        entity=company,
        code=f"L{company[1:]}",
        name=f"Libro principal {company}",
        status="activo",
        currency="NIO",
        default=True,
        is_primary=True,
    )
    banco_gl = Accounts(
        code="1.01.02.001",
        name="Banco en dólares",
        entity=company,
        group=False,
        active=True,
        enabled=True,
        account_type="bank",
    )
    ganancia_gl = Accounts(
        code="4.01.01.001",
        name="Ganancia cambiaria no realizada",
        entity=company,
        group=False,
        active=True,
        enabled=True,
        account_type="income",
    )
    perdida_gl = Accounts(
        code="5.01.02.001",
        name="Pérdida cambiaria no realizada",
        entity=company,
        group=False,
        active=True,
        enabled=True,
        account_type="expense",
    )
    fiscal_year = FiscalYear(
        entity=company,
        name=str(anio),
        year_start_date=date(anio, 1, 1),
        year_end_date=date(anio, 12, 31),
        is_closed=False,
    )
    bank = Bank(name=f"Banco {company}", is_active=True)
    database.session.add_all([ledger, banco_gl, ganancia_gl, perdida_gl, fiscal_year, bank])
    database.session.flush()
    period = AccountingPeriod(
        entity=company,
        fiscal_year_id=fiscal_year.id,
        name=f"Cierre de {mes:02d}",
        start=inicio,
        end=cierre,
        enabled=True,
        is_closed=False,
    )
    bank_account = BankAccount(
        company=company,
        bank_id=bank.id,
        account_name="Cuenta operativa USD",
        account_no=f"USD-{company}",
        gl_account_id=banco_gl.id,
        currency="USD",
        is_active=True,
    )
    database.session.add_all(
        [
            period,
            bank_account,
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.60"), date=cierre),
            CompanyDefaultAccount(
                company=company,
                default_bank=banco_gl.id,
                default_expense=perdida_gl.id,
                default_income=ganancia_gl.id,
                unrealized_exchange_gain_account_id=ganancia_gl.id,
                unrealized_exchange_loss_account_id=perdida_gl.id,
            ),
        ]
    )
    database.session.flush()
    database.session.add(
        GLEntry(
            company=company,
            ledger_id=ledger.id,
            account_id=banco_gl.id,
            bank_account_id=bank_account.id,
            voucher_type="bank_transfer",
            voucher_id=f"OPEN-{company}",
            posting_date=inicio,
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
    return period.id


def test_revaluacion_valida_se_postea_con_controles_internos_activos(business_app):
    """Una revaluación válida se crea y postea sin chocar con la inmutabilidad."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        assert business_app.config["INTERNAL_CONTROLS_ENFORCE"] is True
        period_id = _sembrar_exposicion_bancaria(company)
        usuario_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()

        corrida = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=usuario_id)

        assert corrida.status == "posted"
        assert corrida.docstatus == 1
        assert corrida.document_no
        # 100 USD a 36.60 = 3660 NIO contra 3600 NIO en libros => ganancia de 60 NIO.
        assert corrida.total_gain == Decimal("60.0000")
        assert corrida.total_loss == 0

        persistida = database.session.get(ExchangeRevaluation, str(corrida.id))
        assert persistida is not None
        assert persistida.docstatus == 1
        assert persistida.document_no == corrida.document_no
        asientos = (
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company,
                    voucher_type="exchange_revaluation",
                    voucher_id=str(corrida.id),
                    is_cancelled=False,
                )
            )
            .scalars()
            .all()
        )
        assert len(asientos) == 2
        assert sum(asiento.debit for asiento in asientos) == Decimal("60.0000")
        assert sum(asiento.credit for asiento in asientos) == Decimal("60.0000")


def test_corrida_posteada_sigue_siendo_inmutable_para_controles_internos(business_app):
    """El guard de controles internos protege la corrida ya posteada."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        period_id = _sembrar_exposicion_bancaria(company)
        usuario_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        corrida = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=usuario_id)
        documento_original = corrida.document_no

        with pytest.raises(ValueError, match="Los datos financieros posteados son inmutables"):
            corrida.document_no = f"{documento_original}-MUTADO"
            database.session.flush()
        database.session.rollback()

        persistida = database.session.execute(
            database.select(ExchangeRevaluation).filter_by(company=company, status="posted")
        ).scalar_one()
        assert persistida is not None
        assert persistida.document_no == documento_original
        assert persistida.docstatus == 1


def test_anulacion_de_revalorizacion_funciona_con_controles_activos(business_app):
    """La transición auditada a anulada no choca con el guard de posteo."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        period_id = _sembrar_exposicion_bancaria(company)
        usuario_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        corrida = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=usuario_id)
        run_id = str(corrida.id)

        anulada = ExchangeRevaluationService().void(run_id=run_id, user_id=usuario_id, reason="Prueba de anulación")

        assert anulada.status == "voided"
        assert anulada.docstatus == 2
        assert anulada.voided_by == usuario_id
        assert anulada.voided_at is not None
        assert anulada.reversal_journal_id
        activos = (
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company,
                    voucher_type="exchange_revaluation",
                    voucher_id=run_id,
                    is_cancelled=False,
                    is_reversal=False,
                )
            )
            .scalars()
            .all()
        )
        reversos = (
            database.session.execute(
                database.select(GLEntry).filter_by(
                    company=company,
                    voucher_type="exchange_revaluation",
                    voucher_id=run_id,
                    is_cancelled=False,
                    is_reversal=True,
                )
            )
            .scalars()
            .all()
        )
        assert activos == []
        assert len(reversos) == 2


def test_segunda_corrida_anula_la_anterior_con_controles_activos(business_app):
    """La reejecución anula la corrida posteada previa sin quedar bloqueada."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        period_id = _sembrar_exposicion_bancaria(company)
        usuario_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        primera = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=usuario_id)
        primera_id = str(primera.id)

        segunda = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=usuario_id)

        assert segunda.status == "posted"
        assert segunda.docstatus == 1
        anterior = database.session.get(ExchangeRevaluation, primera_id)
        assert anterior is not None
        assert anterior.status == "voided"
        assert anterior.docstatus == 2


def test_fallo_de_identificador_revierte_la_corrida(business_app, monkeypatch):
    """Si falla la numeración, no queda corrida ni asiento parcial."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        period_id = _sembrar_exposicion_bancaria(company)
        usuario_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()

        def fail_identifier(_self, _run):
            raise RuntimeError("fallo de numeración")

        monkeypatch.setattr(ExchangeRevaluationService, "_assign_identifier", fail_identifier)
        with pytest.raises(RuntimeError, match="fallo de numeración"):
            ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=usuario_id)

        assert database.session.execute(database.select(ExchangeRevaluation).filter_by(company=company)).first() is None
        assert (
            database.session.execute(
                database.select(GLEntry).filter_by(company=company, voucher_type="exchange_revaluation")
            ).first()
            is None
        )


def test_contraasiento_no_puede_revertir_una_linea_ajena(business_app):
    """La exención de reverso exige una línea del mismo documento padre."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        period_id = _sembrar_exposicion_bancaria(company)
        usuario_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        corrida = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=usuario_id)
        modelo = database.session.execute(
            database.select(GLEntry).filter_by(voucher_type="exchange_revaluation", voucher_id=str(corrida.id)).limit(1)
        ).scalar_one()
        ajeno = GLEntry(
            company=company,
            ledger_id=modelo.ledger_id,
            account_id=modelo.account_id,
            voucher_type="sales_invoice",
            voucher_id=f"FACT-{uuid4().hex[:8]}",
            posting_date=modelo.posting_date,
            debit=Decimal("1"),
            credit=Decimal("0"),
        )
        database.session.add(ajeno)
        database.session.commit()

        con_reverso_ajeno = GLEntry(
            company=company,
            ledger_id=modelo.ledger_id,
            account_id=modelo.account_id,
            voucher_type="exchange_revaluation",
            voucher_id=str(corrida.id),
            exchange_revaluation_run_id=str(corrida.id),
            posting_date=modelo.posting_date,
            debit=Decimal("0"),
            credit=Decimal("1"),
            is_reversal=True,
            reversal_of=ajeno.id,
        )
        database.session.add(con_reverso_ajeno)
        with pytest.raises(ValueError, match="Los datos financieros posteados son inmutables"):
            database.session.flush()
        database.session.rollback()

        inexistente = GLEntry(
            company=company,
            ledger_id=modelo.ledger_id,
            account_id=modelo.account_id,
            voucher_type="exchange_revaluation",
            voucher_id=str(corrida.id),
            exchange_revaluation_run_id=str(corrida.id),
            posting_date=modelo.posting_date,
            debit=Decimal("0"),
            credit=Decimal("1"),
            is_reversal=True,
            reversal_of=f"NO-EXISTE-{uuid4().hex[:8]}",
        )
        database.session.add(inexistente)
        with pytest.raises(ValueError, match="Los datos financieros posteados son inmutables"):
            database.session.flush()
        database.session.rollback()


def test_no_se_puede_revertir_dos_veces_la_misma_linea(business_app):
    """Una línea ya revertida no admite un segundo contraasiento."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        period_id = _sembrar_exposicion_bancaria(company)
        usuario_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        corrida = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=usuario_id)
        original = database.session.execute(
            database.select(GLEntry)
            .filter_by(voucher_type="exchange_revaluation", voucher_id=str(corrida.id), is_cancelled=False)
            .limit(1)
        ).scalar_one()
        ExchangeRevaluationService().void(run_id=str(corrida.id), user_id=usuario_id, reason="Primera anulación")

        segundo_reverso = GLEntry(
            company=company,
            ledger_id=original.ledger_id,
            account_id=original.account_id,
            voucher_type="exchange_revaluation",
            voucher_id=str(corrida.id),
            exchange_revaluation_run_id=str(corrida.id),
            posting_date=original.posting_date,
            debit=Decimal("0"),
            credit=Decimal("1"),
            is_reversal=True,
            reversal_of=original.id,
        )
        database.session.add(segundo_reverso)
        with pytest.raises(ValueError, match="Los datos financieros posteados son inmutables"):
            database.session.flush()
        database.session.rollback()
