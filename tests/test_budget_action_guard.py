# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Acción correcta del guard de compañía en presupuestos.

Escenario de negocio: un usuario con permiso de aprobar/cerrar pero sin permiso
de crear puede aprobar y cerrar un presupuesto de su compañía. El guard de
compañía debe exigir la acción del endpoint, no siempre ``crear``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Book,
    Budget,
    BudgetLine,
    CostCenter,
    Currency,
    Entity,
    FiscalYear,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre
from cacao_accounting.contabilidad.presupuesto import enforce_budget_company_access

CONTRASENA = "presupuesto-acciones-2026"
FECHA = date(2026, 1, 1)


@pytest.fixture
def presupuesto_acciones():
    """Presupuesto borrador y usuario con aprobar/cerrar, sin crear."""
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
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
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
                    id="aprobador",
                    user="aprobador",
                    name="Aprobador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="operador",
                    user="operador",
                    name="Operador de presupuesto",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="aprobador", company_code="cacao"),
                UserCompanyAccess(user_id="operador", company_code="cacao"),
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
        anio = FiscalYear(
            entity="cacao",
            name="2026",
            year_start_date=FECHA,
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        cuenta = Accounts(
            code="5.01.01.001",
            name="Gastos",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="expense",
        )
        centro = CostCenter(
            code="CC-1",
            name="Centro",
            entity="cacao",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add_all([libro, anio, cuenta, centro])
        database.session.flush()
        periodo = AccountingPeriod(
            entity="cacao",
            fiscal_year_id=anio.id,
            name="2026-01",
            start=FECHA,
            end=date(2026, 1, 31),
            enabled=True,
            is_closed=False,
        )
        database.session.add(periodo)
        database.session.flush()
        presupuesto = Budget(
            company="cacao",
            ledger_id=libro.id,
            fiscal_year_id=anio.id,
            budget_code="B-1",
            name="Presupuesto",
            currency_id="NIO",
            status="draft",
        )
        database.session.add(presupuesto)
        database.session.flush()
        database.session.add(
            BudgetLine(
                budget_id=presupuesto.id,
                account_id=cuenta.id,
                cost_center_id=centro.id,
                period_id=periodo.id,
                amount=Decimal("100"),
            )
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        rol = Roles(name="aprobador_presupuesto", note="Aprueba y cierra")
        database.session.add(rol)
        database.session.flush()
        database.session.add(
            RolesAccess(
                rol_id=rol.id,
                module_id=obtener_id_modulo_por_nombre("accounting"),
                access=True,
                update=False,
                set_null=False,
                approve=True,
                bi=False,
                close=True,
                setup=False,
                view=True,
                create=False,
                edit=False,
                delete=False,
                import_=False,
                report=False,
                request=False,
                validate=False,
            )
        )
        database.session.add(RolesUser(user_id="aprobador", role_id=rol.id, active=True))
        rol_operador = Roles(name="operador_presupuesto", note="Importa y elimina")
        database.session.add(rol_operador)
        database.session.flush()
        database.session.add(
            RolesAccess(
                rol_id=rol_operador.id,
                module_id=obtener_id_modulo_por_nombre("accounting"),
                access=True,
                update=False,
                set_null=False,
                approve=False,
                bi=False,
                close=False,
                setup=False,
                view=True,
                create=False,
                edit=False,
                delete=True,
                import_=True,
                report=False,
                request=False,
                validate=False,
            )
        )
        database.session.add(RolesUser(user_id="operador", role_id=rol_operador.id, active=True))
        database.session.commit()
        presupuesto_id = presupuesto.id
        linea_id = database.session.execute(database.select(BudgetLine)).scalar_one().id
    yield application, {"presupuesto": presupuesto_id, "linea": linea_id}
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client, usuario: str = "aprobador") -> None:
    response = client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_aprobar_exige_autorizar_no_crear(presupuesto_acciones):
    """Aprobar usa el permiso autorizar y no exige crear."""
    application, ids = presupuesto_acciones
    client = application.test_client()
    _iniciar(client)

    response = client.post(f"/accounting/presupuestos/{ids['presupuesto']}/approve")

    assert response.status_code == 302
    with application.app_context():
        assert database.session.get(Budget, ids["presupuesto"]).status == "approved"


def test_cerrar_exige_cerrar_no_crear(presupuesto_acciones):
    """Cerrar usa el permiso cerrar y no exige crear."""
    application, ids = presupuesto_acciones
    client = application.test_client()
    _iniciar(client)
    client.post(f"/accounting/presupuestos/{ids['presupuesto']}/approve")

    response = client.post(f"/accounting/presupuestos/{ids['presupuesto']}/close")

    assert response.status_code == 302
    with application.app_context():
        assert database.session.get(Budget, ids["presupuesto"]).status == "closed"


def test_importar_exige_importar_no_crear(presupuesto_acciones):
    """Importar usa el permiso importar y no exige crear."""
    application, ids = presupuesto_acciones

    with application.test_request_context(f"/accounting/presupuestos/{ids['presupuesto']}/import", method="POST"):
        from flask_login import login_user

        usuario = database.session.execute(database.select(User).filter_by(user="operador")).scalar_one()
        login_user(usuario)
        enforce_budget_company_access()


def test_eliminar_linea_exige_eliminar_no_crear(presupuesto_acciones):
    """Eliminar línea usa el permiso eliminar y no exige crear."""
    application, ids = presupuesto_acciones
    client = application.test_client()
    _iniciar(client, "operador")

    response = client.post(f"/accounting/presupuestos/line/{ids['linea']}/delete")

    assert response.status_code == 302
    with application.app_context():
        assert database.session.get(BudgetLine, ids["linea"]) is None
