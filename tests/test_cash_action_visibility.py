# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1981: las acciones de caja se ocultan sin permiso de creación/edición/anulación.

El backend ya responde 403. La interfaz tampoco debe ofrecer enlaces que el
usuario no puede ejecutar, ni en las listas ni en el detalle de cuenta bancaria.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Bank,
    BankAccount,
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

CONTRASENA = "cash-visibilidad-2026"


def _cliente(app, user_id: str):
    """Cliente autenticado para el usuario indicado."""
    with app.app_context():
        auth_version = database.session.get(User, user_id).auth_version
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    return client


@pytest.fixture
def acciones_caja():
    """Datos de caja con administrador y un lector sin permisos de escritura."""
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
            ]
        )
        database.session.flush()
        database.session.add(Book(code="DEFAULT", name="Libro", entity="cacao", currency="NIO", status="activo"))
        database.session.flush()
        admin = User(
            id="admin-caja",
            user="admin-caja",
            name="Administrador de Caja",
            password=proteger_passwd(CONTRASENA),
            classification="admin",
            active=True,
            company="cacao",
        )
        lector = User(
            id="lector-caja",
            user="lector-caja",
            name="Lector de Caja",
            password=proteger_passwd(CONTRASENA),
            classification="user",
            active=True,
            company="cacao",
        )
        database.session.add_all([admin, lector])
        database.session.flush()
        database.session.add_all(
            [
                UserCompanyAccess(user_id=admin.id, company_code="cacao"),
                UserCompanyAccess(user_id=lector.id, company_code="cacao"),
            ]
        )
        rol = Roles(name="lector-caja", note="Solo consulta de caja")
        database.session.add(rol)
        database.session.flush()
        modulo = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one()
        database.session.add_all(
            [
                RolesAccess(rol_id=rol.id, module_id=modulo.id, access=True, view=True),
                RolesUser(user_id=lector.id, role_id=rol.id, active=True),
            ]
        )
        cuenta_banco = Accounts(
            code="1.01.02.001",
            name="Banco",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="bank",
        )
        cuenta_caja = Accounts(
            code="1.01.05.001",
            name="Caja Chica",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="petty_cash",
        )
        database.session.add_all([cuenta_banco, cuenta_caja])
        database.session.flush()
        banco = Bank(name="Banco de Prueba", swift_code="BPRONIMM")
        database.session.add(banco)
        database.session.flush()
        cuenta_bancaria = BankAccount(
            bank_id=banco.id,
            company="cacao",
            account_name="Cuenta Operativa",
            account_no="001-1981",
            currency="NIO",
            gl_account_id=cuenta_banco.id,
        )
        fondo = PettyCashAccount(
            company="cacao",
            account_id=cuenta_caja.id,
            name="Fondo de Prueba",
            currency="NIO",
            float_amount=Decimal("500"),
            is_default=True,
            is_active=True,
        )
        database.session.add_all([cuenta_bancaria, fondo])
        database.session.flush()
        vale = PettyCashVoucher(
            company="cacao",
            petty_cash_id=fondo.id,
            voucher_no="VALE-1981",
            voucher_status="entregado",
            delivered_to="Empleado",
            concept="Viáticos",
            amount=Decimal("25"),
            posting_date=date(2026, 11, 20),
            transaction_currency="NIO",
        )
        gasto = PettyCashExpense(
            company="cacao",
            petty_cash_id=fondo.id,
            concept="Suministros",
            expense_account_code="5.01.01.001",
            amount=Decimal("10"),
            posting_date=date(2026, 11, 20),
            docstatus=1,
            document_no="GTO-1981",
            transaction_currency="NIO",
        )
        database.session.add_all([vale, gasto])
        database.session.commit()
        ids = {"banco": cuenta_bancaria.id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_lector_no_ve_acciones_de_escritura(acciones_caja):
    """La consulta no ofrece alta, entrega, liquidación, cancelación ni anulación."""
    application, ids = acciones_caja
    client = _cliente(application, "lector-caja")

    detalle = client.get(f"/cash_management/bank-account/{ids['banco']}")
    assert detalle.status_code == 200
    assert "/cash_management/bank-account/new" not in detalle.get_data(as_text=True)

    for ruta, enlaces in (
        ("/cash_management/petty-cash/list", ("/cash_management/petty-cash/new",)),
        (
            "/cash_management/petty-cash-voucher/list",
            ("/cash_management/petty-cash-voucher/new", "Liquidar", "Entregar", "Cancelar"),
        ),
        ("/cash_management/petty-cash-expense/list", ("/cash_management/petty-cash-expense/new", "Anular")),
    ):
        response = client.get(ruta)
        assert response.status_code == 200
        cuerpo = response.get_data(as_text=True)
        for enlace in enlaces:
            assert enlace not in cuerpo, f"{enlace} no debe ofrecerse sin permiso en {ruta}."


def test_administrador_conserva_las_acciones(acciones_caja):
    """El administrador sigue viendo los controles que el backend le permite."""
    application, ids = acciones_caja
    client = _cliente(application, "admin-caja")

    detalle = client.get(f"/cash_management/bank-account/{ids['banco']}")
    assert detalle.status_code == 200
    assert "/cash_management/bank-account/new" in detalle.get_data(as_text=True)

    vales = client.get("/cash_management/petty-cash-voucher/list")
    assert vales.status_code == 200
    cuerpo_vales = vales.get_data(as_text=True)
    assert "/cash_management/petty-cash-voucher/new" in cuerpo_vales
    assert "Liquidar" in cuerpo_vales
    assert "Cancelar" in cuerpo_vales

    gastos = client.get("/cash_management/petty-cash-expense/list")
    assert gastos.status_code == 200
    cuerpo_gastos = gastos.get_data(as_text=True)
    assert "/cash_management/petty-cash-expense/new" in cuerpo_gastos
    assert "Anular" in cuerpo_gastos
