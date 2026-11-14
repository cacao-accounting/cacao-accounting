# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""La revaluación cambiaria se rechaza cuando falta la tasa de cierre (#2121).

Escenario de negocio: una compañía con libro resumen en NIO y un libro
secundario en EUR expone un banco en USD cuya apertura solo vive en el libro
secundario. El cálculo de líneas usa la tasa USD->EUR, pero los totales de la
corrida se convierten desde la moneda de cada libro (EUR) hacia la moneda del
libro resumen (NIO). Si no existe tasa EUR->NIO la corrida debe rechazarse con
``ExchangeRevaluationError`` y no puede quedar una corrida persistida con
totales parciales en cero. Con la tasa sembrada, la corrida se postea con los
totales convertidos correctos.
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
from cacao_accounting.contabilidad.exchange_revaluation_service import (
    ExchangeRevaluationError,
    ExchangeRevaluationService,
)
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
    PeriodCloseCheck,
    PeriodCloseRun,
    User,
    database,
)

pytestmark = pytest.mark.database

CONTRASENA = "Revaluacion-Test-2026!"


@pytest.fixture
def business_app(tmp_path):
    """Crea una aplicación real con una base aislada en el motor configurado."""
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
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _mes_de_cierre_libre() -> tuple[int, int]:
    """Elige un mes de cierre sin tasas que contamine el escenario multi-moneda.

    El par EUR<->NIO debe carecer de tasas en cualquier fecha previa al cierre
    (el servicio recurre a la tasa más próxima) y ninguno de los pares usados
    puede tener una tasa exactamente en la fecha de cierre (evita colisiones en
    bases compartidas cuando se valida contra un motor externo).
    """
    filas = database.session.execute(
        database.select(ExchangeRate.origin, ExchangeRate.destination, ExchangeRate.date).where(
            ExchangeRate.origin.in_(["USD", "EUR", "NIO"]), ExchangeRate.destination.in_(["USD", "EUR", "NIO"])
        )
    ).all()
    for anio in range(2001, 2027):
        for mes in range(2, 12):
            cierre = date(anio, mes, calendar.monthrange(anio, mes)[1])
            contaminado = any(
                (par := frozenset((origen, destino))) in ({frozenset(("EUR", "NIO"))} if tasa_fecha <= cierre else set())
                or (par in {frozenset(("USD", "EUR")), frozenset(("EUR", "NIO"))} and tasa_fecha == cierre)
                for origen, destino, tasa_fecha in filas
            )
            if not contaminado:
                return anio, mes
    raise AssertionError("No hay mes libre para sembrar el escenario de tasas.")


def _sembrar_libro_secundario_en_euros(company: str, *, con_tasa_eur_nio: bool) -> tuple[str, str, str, str, str]:
    """Siembra compañía multi-libro con banco en USD expuesto solo en el libro EUR.

    Devuelve ``(company, period_id, libro_eur_id, banco_gl_id, ganancia_gl_id)``.
    La apertura del banco se registra únicamente en el libro secundario EUR con
    valor funcional histórico de 90 EUR por 100 USD (tasa 0.90), de modo que el
    libro resumen NIO queda sin asientos y los totales de la corrida deban
    convertirse con la tasa de cierre EUR->NIO.
    """
    anio, mes = _mes_de_cierre_libre()
    inicio = date(anio, mes, 1)
    cierre = date(anio, mes, calendar.monthrange(anio, mes)[1])
    database.session.add_all(
        [
            Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
            Currency(code="USD", name="Dólar", decimals=2, active=True),
            Currency(code="EUR", name="Euro", decimals=2, active=True),
            Modules(module="accounting", default=False, enabled=True),
            Entity(
                code=company,
                name=f"Empresa multi-moneda {company}",
                company_name=f"Empresa multi-moneda {company} SA",
                tax_id=f"TAX-{company}",
                currency="NIO",
                enabled=True,
                status="default",
            ),
        ]
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
    libro_resumen = Book(
        entity=company,
        code=f"L{company[1:]}",
        name=f"Libro fiscal {company}",
        status="activo",
        currency="NIO",
        default=True,
        is_primary=True,
    )
    libro_eur = Book(
        entity=company,
        code=f"E{company[2:]}",
        name=f"Libro consolidado EUR {company}",
        status="activo",
        currency="EUR",
        is_primary=False,
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
    database.session.add_all([libro_resumen, libro_eur, banco_gl, ganancia_gl, perdida_gl, fiscal_year, bank])
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
    database.session.add_all([period, bank_account])
    database.session.flush()
    tasas = [ExchangeRate(origin="USD", destination="EUR", rate=Decimal("1.10"), date=cierre)]
    if con_tasa_eur_nio:
        tasas.append(ExchangeRate(origin="EUR", destination="NIO", rate=Decimal("40"), date=cierre))
    database.session.add_all(
        [
            *tasas,
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
            ledger_id=libro_eur.id,
            account_id=banco_gl.id,
            bank_account_id=bank_account.id,
            voucher_type="bank_transfer",
            voucher_id=f"OPEN-{company}",
            posting_date=inicio,
            debit=Decimal("90"),
            credit=Decimal("0"),
            debit_in_account_currency=Decimal("100"),
            credit_in_account_currency=Decimal("0"),
            account_currency="USD",
            company_currency="EUR",
            exchange_rate=Decimal("0.90"),
        )
    )
    database.session.commit()
    return company, period.id, libro_eur.id, banco_gl.id, ganancia_gl.id


def test_revaluacion_sin_tasa_de_cierre_se_rechaza_sin_dejar_corrida(business_app):
    """Sin tasa EUR->NIO la corrida se rechaza y no persiste evidencia parcial."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        company, period_id, libro_eur_id, banco_gl_id, _ganancia_gl_id = _sembrar_libro_secundario_en_euros(
            company, con_tasa_eur_nio=False
        )

        with pytest.raises(ExchangeRevaluationError, match="Falta tasa de cierre para EUR -> NIO"):
            ExchangeRevaluationService().run(company=company, period_id=period_id)

        assert database.session.execute(database.select(ExchangeRevaluation).filter_by(company=company)).scalars().all() == []
        assert (
            database.session.execute(database.select(GLEntry).filter_by(company=company, voucher_type="exchange_revaluation"))
            .scalars()
            .all()
            == []
        )
        saldo_banco = database.session.execute(
            database.select(database.func.coalesce(database.func.sum(GLEntry.debit - GLEntry.credit), 0)).where(
                GLEntry.company == company, GLEntry.ledger_id == libro_eur_id, GLEntry.account_id == banco_gl_id
            )
        ).scalar_one()
        assert saldo_banco == Decimal("90")


def test_revaluacion_con_tasa_sembrada_postea_totales_convertidos(business_app):
    """Con la tasa EUR->NIO sembrada la corrida se postea con totales correctos."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        company, period_id, libro_eur_id, banco_gl_id, ganancia_gl_id = _sembrar_libro_secundario_en_euros(
            company, con_tasa_eur_nio=True
        )
        usuario_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()

        corrida = ExchangeRevaluationService().run(company=company, period_id=period_id, user_id=usuario_id)

        assert corrida.status == "posted"
        assert corrida.docstatus == 1
        assert corrida.document_no
        assert corrida.currency == "NIO"
        assert corrida.affected_documents_count == 1
        # 100 USD a 1.10 = 110 EUR contra 90 EUR en libros => diferencia de 20 EUR,
        # convertida al libro resumen con la tasa EUR->NIO de 40 => 800 NIO.
        assert corrida.total_gain == Decimal("800.0000")
        assert corrida.total_loss == 0

        persistida = database.session.get(ExchangeRevaluation, str(corrida.id))
        assert persistida is not None
        assert persistida.status == "posted"
        assert persistida.total_gain == Decimal("800.0000")
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
        assert all(asiento.ledger_id == libro_eur_id for asiento in asientos)
        asiento_banco = next(asiento for asiento in asientos if asiento.account_id == banco_gl_id)
        assert asiento_banco.debit == Decimal("20.0000")
        assert asiento_banco.credit == 0
        asiento_resultado = next(asiento for asiento in asientos if asiento.account_id == ganancia_gl_id)
        assert asiento_resultado.credit == Decimal("20.0000")
        assert asiento_resultado.debit == 0


def test_ruta_de_cierre_registra_fallo_por_tasa_faltante(business_app):
    """La ruta del cierre mensual captura el error y registra el control fallido."""
    company = f"R{uuid4().hex[:9]}"
    with business_app.app_context():
        company, period_id, _libro_eur_id, _banco_gl_id, _ganancia_gl_id = _sembrar_libro_secundario_en_euros(
            company, con_tasa_eur_nio=False
        )
        usuario_id = database.session.execute(database.select(User.id).filter_by(company=company)).scalar_one()
        cierre = PeriodCloseRun(company=company, period_id=period_id, run_status="open")
        database.session.add(cierre)
        database.session.commit()
        cierre_id = cierre.id

        cliente = business_app.test_client()
        with cliente.session_transaction() as sesion:
            sesion["_user_id"] = str(usuario_id)
            sesion["_fresh"] = True
        respuesta = cliente.post(f"/accounting/period-close/monthly/{cierre_id}/exchange-revaluation")

        assert respuesta.status_code == 302
        control = database.session.execute(
            database.select(PeriodCloseCheck).filter_by(close_run_id=cierre_id, check_type="exchange_revaluation")
        ).scalar_one()
        assert control.check_status == "failed"
        assert "Falta tasa de cierre para EUR -> NIO" in control.message
        assert database.session.execute(database.select(ExchangeRevaluation).filter_by(company=company)).scalars().all() == []
