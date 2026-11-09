# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La revalorización postea en Cloud con controles internos activos.

Escenario de negocio (issue #2119): la corrida nacía con docstatus=1 y luego
recibía posting_date/document_no de la serie; el guard de inmutabilidad
rechazaba la mutación y el alta fallaba antes de terminar.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.exchange_revaluation_service import (
    EXCHANGE_REVALUATION_STATUS_NO_CHANGES,
    ExchangeRevaluationService,
)
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Book,
    CompanyDefaultAccount,
    Currency,
    Entity,
    User,
    database,
)

FECHA = date(2026, 10, 31)


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        libro = Book(
            entity="cacao",
            code="LOCAL",
            name="Principal",
            status="activo",
            currency="NIO",
            default=True,
            is_primary=True,
        )
        ganancia = Accounts(
            code="4.01.01.001",
            name="Ganancia cambiaria",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="income",
        )
        perdida = Accounts(
            code="5.01.02.001",
            name="Pérdida cambiaria",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="expense",
        )
        periodo = AccountingPeriod(
            entity="cacao",
            name="OCT-2026",
            start=date(2026, 10, 1),
            end=FECHA,
            enabled=True,
            is_closed=False,
        )
        database.session.add_all([libro, ganancia, perdida, periodo])
        database.session.flush()
        database.session.add(
            CompanyDefaultAccount(
                company="cacao",
                unrealized_exchange_gain_account_id=ganancia.id,
                unrealized_exchange_loss_account_id=perdida.id,
            )
        )
        database.session.commit()
        return application, periodo.id


def test_la_corrida_sin_cambios_posta_con_controles_activos():
    """El identificador se asigna antes de marcar docstatus=1."""
    application, period_id = _crear_app()
    try:
        with application.app_context():
            run = ExchangeRevaluationService().run(company="cacao", period_id=period_id, user_id="admin")

            assert run.status == EXCHANGE_REVALUATION_STATUS_NO_CHANGES
            assert run.docstatus == 1
            assert run.document_no
            assert run.id
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
