# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1265: la caja chica predeterminada solo usa cuentas utilizables."""

from __future__ import annotations

from cacao_accounting.bancos.services import create_default_petty_cash
from cacao_accounting.database import Accounts, PettyCashAccount, User, database


def _cuenta(company: str, code: str, *, active: bool = True, enabled: bool = True) -> Accounts:
    account = Accounts(
        entity=company,
        code=code,
        name=f"Caja chica {code}",
        account_type="petty_cash",
        group=False,
        active=active,
        enabled=enabled,
    )
    database.session.add(account)
    return account


def _limpiar_fondos(company: str) -> None:
    """Elimina solo los fondos de caja chica de la compañía."""

    for record in database.session.execute(database.select(PettyCashAccount).filter_by(company=company)).scalars():
        database.session.delete(record)
    database.session.flush()


def _limpiar_cuentas(company: str, codes: tuple[str, ...]) -> None:
    """Elimina solo las cuentas de caja chica creadas por la prueba."""

    for account in database.session.execute(
        database.select(Accounts).filter_by(entity=company).where(Accounts.code.in_(codes))
    ).scalars():
        database.session.delete(account)
    database.session.flush()


def test_setup_omite_cuentas_inactivas_y_elige_la_activa(app, entorno_contable):
    """Una cuenta petty_cash inactiva no se elige sobre la activa disponible."""
    company = "cacao"
    with app.app_context():
        _limpiar_fondos(company)
        _cuenta(company, "9205", active=False)
        _cuenta(company, "9206", active=True)
        database.session.flush()

        fondo = create_default_petty_cash(company)
        assert fondo is not None
        cuenta = database.session.get(Accounts, fondo.account_id)
        assert cuenta.code == "9206"
        _limpiar_fondos(company)
        _limpiar_cuentas(company, ("9205", "9206"))
        database.session.commit()


def test_setup_omite_cuentas_deshabilitadas(app, entorno_contable):
    """Una cuenta petty_cash deshabilitada tampoco se elige."""
    company = "cacao"
    with app.app_context():
        _limpiar_fondos(company)
        _cuenta(company, "9207", enabled=False)
        _cuenta(company, "9208", active=True, enabled=True)
        database.session.flush()

        fondo = create_default_petty_cash(company)
        assert fondo is not None
        cuenta = database.session.get(Accounts, fondo.account_id)
        assert cuenta.code == "9208"
        _limpiar_fondos(company)
        _limpiar_cuentas(company, ("9207", "9208"))
        database.session.commit()


def test_setup_sin_cuenta_utilizable_no_crea_fondo(app, entorno_contable):
    """Si solo hay cuentas inactivas, el setup deja el fondo sin crear."""
    company = "cacao"
    with app.app_context():
        _limpiar_fondos(company)
        _cuenta(company, "9209", active=False)
        _cuenta(company, "9210", enabled=False)
        database.session.flush()

        assert create_default_petty_cash(company) is None
        assert database.session.execute(database.select(PettyCashAccount).filter_by(company=company)).first() is None
        _limpiar_cuentas(company, ("9209", "9210"))
        database.session.commit()


def test_setup_idempotente_conserva_el_fondo_existente(app, entorno_contable):
    """Si ya existe un fondo por defecto, no se crea otro ni se reasigna."""
    company = "cacao"
    with app.app_context():
        _limpiar_fondos(company)
        account = _cuenta(company, "9211", active=True)
        database.session.flush()
        admin_id = database.session.execute(database.select(User.id).filter_by(user="admin")).scalar_one()
        database.session.add(
            PettyCashAccount(
                company=company,
                name="Fondo existente",
                account_id=account.id,
                custodian_id=admin_id,
                is_default=True,
                is_active=True,
            )
        )
        database.session.flush()

        fondo = create_default_petty_cash(company)
        assert fondo is not None
        assert fondo.name == "Fondo existente"
        assert len(database.session.execute(database.select(PettyCashAccount).filter_by(company=company)).scalars().all()) == 1
        _limpiar_fondos(company)
        _limpiar_cuentas(company, ("9211",))
        database.session.commit()
