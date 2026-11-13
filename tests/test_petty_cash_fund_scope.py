# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Alcance por compañía del fondo de caja chica en la reposición.

Escenario de negocio: una tesorera autorizada solo en ``alpha`` no debe poder
leer los gastos pendientes de reposición de un fondo de ``beta`` fabricando el
``petty_cash_id`` en la URL. La autorización del POST no protege la lectura GET
previa; el fondo solicitado debe pertenecer al alcance vigente antes de
consultar sus gastos.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Book,
    Currency,
    Entity,
    Modules,
    PettyCashAccount,
    PettyCashExpense,
    PettyCashVoucher,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "caja-fondo-scope-2026"
FECHA = date(2026, 10, 20)


@pytest.fixture
def caja_multicompania():
    """Cloud con fondos de caja chica y gastos en alpha y beta."""
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
                Modules(module="cash", default=False, enabled=True),
                Modules(module="accounting", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name="Beta SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Book(code="ALPHA", name="Libro Alpha", entity="alpha", currency="NIO", status="activo"),
                Book(code="BETA", name="Libro Beta", entity="beta", currency="NIO", status="activo"),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                User(
                    id="tesorera",
                    user="tesorera",
                    name="Tesorera Alpha",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add(
            UserCompanyAccess(user_id="tesorera", company_code="alpha"),
        )
        database.session.flush()
        cuentas = {
            "alpha": Accounts(
                code="1.01.05.001",
                name="Caja Chica Alpha",
                entity="alpha",
                group=False,
                active=True,
                enabled=True,
                account_type="petty_cash",
            ),
            "beta": Accounts(
                code="1.01.05.001",
                name="Caja Chica Beta",
                entity="beta",
                group=False,
                active=True,
                enabled=True,
                account_type="petty_cash",
            ),
        }
        database.session.add_all(cuentas.values())
        database.session.flush()
        fondos = {
            company: PettyCashAccount(
                company=company,
                account_id=cuenta.id,
                name=f"Fondo {company}",
                currency="NIO",
                float_amount=Decimal("1000"),
                is_default=True,
                is_active=True,
            )
            for company, cuenta in cuentas.items()
        }
        database.session.add_all(fondos.values())
        database.session.flush()
        database.session.add_all(
            [
                PettyCashExpense(
                    company="alpha",
                    petty_cash_id=fondos["alpha"].id,
                    concept="Cafe alpha",
                    expense_account_code="5.01.01.001",
                    amount=Decimal("10"),
                    posting_date=FECHA,
                    docstatus=1,
                ),
                PettyCashExpense(
                    company="beta",
                    petty_cash_id=fondos["beta"].id,
                    concept="Taxi beta SECRET",
                    expense_account_code="5.01.01.001",
                    amount=Decimal("25"),
                    posting_date=FECHA,
                    docstatus=1,
                ),
            ]
        )
        vales = {
            "alpha": PettyCashVoucher(
                company="alpha",
                petty_cash_id=fondos["alpha"].id,
                voucher_no="VALE-ALPHA",
                voucher_status="entregado",
                delivered_to="Ana Alpha",
                concept="Cafe alpha voucher",
                amount=Decimal("10"),
                posting_date=FECHA,
                docstatus=1,
            ),
            "beta": PettyCashVoucher(
                company="beta",
                petty_cash_id=fondos["beta"].id,
                voucher_no="VALE-BETA",
                voucher_status="entregado",
                delivered_to="Bob",
                concept="Foreign expense",
                amount=Decimal("99"),
                posting_date=FECHA,
                docstatus=1,
            ),
        }
        database.session.add_all(vales.values())
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("tesorera", "head_of_treasury")
        database.session.commit()
        ids = {
            "alpha": fondos["alpha"].id,
            "beta": fondos["beta"].id,
            "vale_alpha": vales["alpha"].id,
            "vale_beta": vales["beta"].id,
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "tesorera", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def _configurar_permiso_caja(application, *, anular: bool, editar: bool) -> None:
    """Asigna al usuario una acción de caja precisa para comprobar guards HTTP."""
    with application.app_context():
        user_id = "tesorera"
        database.session.execute(database.delete(RolesUser).where(RolesUser.user_id == user_id))
        role = Roles(name=f"cash-cancel-{anular}-{editar}", note="Permiso acotado para prueba")
        database.session.add(role)
        database.session.flush()
        cash_module = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one()
        database.session.add(
            RolesAccess(
                rol_id=role.id,
                module_id=cash_module.id,
                access=True,
                set_null=anular,
                edit=editar,
            )
        )
        database.session.add(RolesUser(user_id=user_id, role_id=role.id, active=True))
        database.session.commit()


def test_reposicion_no_expone_gastos_de_un_fondo_ajeno(caja_multicompania):
    """El GET rechaza un fondo de beta antes de consultar sus gastos."""
    application, ids = caja_multicompania
    client = application.test_client()
    _iniciar(client)

    response = client.get(f"/cash_management/petty-cash-replenishment/new?petty_cash_id={ids['beta']}&company=beta")

    assert response.status_code == 403
    cuerpo = response.get_data(as_text=True)
    assert "Taxi beta SECRET" not in cuerpo


def test_reposicion_muestra_gastos_del_fondo_propio(caja_multicompania):
    """Control positivo: el fondo autorizado sigue disponible."""
    application, ids = caja_multicompania
    client = application.test_client()
    _iniciar(client)

    response = client.get(f"/cash_management/petty-cash-replenishment/new?petty_cash_id={ids['alpha']}")

    assert response.status_code == 200
    assert "Cafe alpha" in response.get_data(as_text=True)


def test_gasto_no_precarga_un_vale_de_otra_compania(caja_multicompania):
    """El formulario rechaza el vale ajeno antes de copiar sus datos."""
    application, ids = caja_multicompania
    client = application.test_client()
    _iniciar(client)

    response = client.get(f"/cash_management/petty-cash-expense/new?voucher_id={ids['vale_beta']}")

    assert response.status_code == 403
    cuerpo = response.get_data(as_text=True)
    assert "Bob" not in cuerpo
    assert "Foreign expense" not in cuerpo


def test_gasto_precarga_el_vale_propio(caja_multicompania):
    """Control positivo: el vale de la compañía autorizada sí se precarga."""
    application, ids = caja_multicompania
    client = application.test_client()
    _iniciar(client)

    response = client.get(f"/cash_management/petty-cash-expense/new?voucher_id={ids['vale_alpha']}")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Ana Alpha" in cuerpo
    assert "Cafe alpha voucher" in cuerpo


def test_anular_gasto_usa_permiso_anular_y_alcance_de_compania(caja_multicompania):
    """Una persona con permiso anular, sin editar, puede anular en su compañía."""
    application, _ = caja_multicompania
    _configurar_permiso_caja(application, anular=True, editar=False)
    with application.app_context():
        expense = database.session.execute(
            database.select(PettyCashExpense).filter_by(company="alpha", concept="Cafe alpha")
        ).scalar_one()
        expense_id = expense.id

    client = application.test_client()
    _iniciar(client)
    response = client.post(f"/cash_management/petty-cash-expense/{expense_id}/cancel")

    assert response.status_code == 302
    with application.app_context():
        expense = database.session.get(PettyCashExpense, expense_id)
        assert expense is not None and expense.docstatus == 2


def test_anular_gasto_exige_acceso_a_la_compania(caja_multicompania):
    """El permiso anular no permite actuar sobre una compañía fuera de alcance."""
    application, _ = caja_multicompania
    _configurar_permiso_caja(application, anular=True, editar=False)
    with application.app_context():
        expense = database.session.execute(
            database.select(PettyCashExpense).filter_by(company="alpha", concept="Cafe alpha")
        ).scalar_one()
        expense_id = expense.id
        database.session.execute(
            database.delete(UserCompanyAccess).where(
                UserCompanyAccess.user_id == "tesorera",
                UserCompanyAccess.company_code == "alpha",
            )
        )
        database.session.commit()

    client = application.test_client()
    _iniciar(client)
    response = client.post(f"/cash_management/petty-cash-expense/{expense_id}/cancel")

    assert response.status_code == 403
    with application.app_context():
        expense = database.session.get(PettyCashExpense, expense_id)
        assert expense is not None and expense.docstatus == 1


def test_editar_sin_anular_no_permite_cancelar_gasto(caja_multicompania):
    """El guard de la ruta sigue exigiendo anular, aunque exista permiso editar."""
    application, _ = caja_multicompania
    _configurar_permiso_caja(application, anular=False, editar=True)
    with application.app_context():
        expense = database.session.execute(
            database.select(PettyCashExpense).filter_by(company="alpha", concept="Cafe alpha")
        ).scalar_one()
        expense_id = expense.id

    client = application.test_client()
    _iniciar(client)
    response = client.post(f"/cash_management/petty-cash-expense/{expense_id}/cancel")

    assert response.status_code == 403
    with application.app_context():
        expense = database.session.get(PettyCashExpense, expense_id)
        assert expense is not None and expense.docstatus == 1
