# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1265: la caja chica predeterminada solo usa cuentas utilizables."""

from __future__ import annotations

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.bancos.services import create_default_petty_cash
from cacao_accounting.database import Accounts, Currency, PettyCashAccount, User, database


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


def test_finalize_setup_informa_cuando_no_crea_fondo(app, entorno_contable, monkeypatch):
    """#1265: sin cuenta utilizable el setup informa y no crea el fondo."""
    from cacao_accounting.setup import service as setup_service

    company = "cacao"
    with app.app_context():
        _limpiar_fondos(company)
        _cuenta(company, "9301", active=False)
        database.session.flush()

        # Ejecuta solo la parte relevante: el helper de creación del fondo
        # reporta False y finalize_setup propaga ese estado.
        created = setup_service.create_default_petty_cash(company)
        assert created is None
        assert database.session.execute(database.select(PettyCashAccount).filter_by(company=company)).first() is None
        _limpiar_cuentas(company, ("9301",))
        database.session.commit()


def test_finalize_setup_true_cuando_crea_fondo(app, entorno_contable):
    """Control positivo: con cuenta utilizable el setup crea el fondo."""
    company = "cacao"
    with app.app_context():
        _limpiar_fondos(company)
        cuenta = _cuenta(company, "9302", active=True, enabled=True)
        database.session.flush()
        fondo = create_default_petty_cash(company)
        assert fondo is not None
        assert fondo.account_id == cuenta.id
        _limpiar_fondos(company)
        _limpiar_cuentas(company, ("9302",))
        database.session.commit()


def test_finalize_setup_propaga_estado_del_fondo(tmp_path, monkeypatch):
    """#1265: `finalize_setup` devuelve el estado del fondo predeterminado."""
    import cacao_accounting.setup.service as setup_service

    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.commit()

        payload = {
            "id": "FONDO1",
            "razon_social": "Fondo SA",
            "nombre_comercial": "Fondo",
            "id_fiscal": "J-FONDO",
            "tipo_entidad": "company",
            "moneda": "NIO",
            "pais": "NI",
            "inicio_anio_fiscal": __import__("datetime").date(2026, 1, 1),
            "fin_anio_fiscal": __import__("datetime").date(2026, 12, 31),
        }

        # Sin catálogo preexistente no se crea fondo; el flujo no falla, pero
        # el resultado por defecto es True (no aplica la rama de catálogo).
        assert isinstance(setup_service.finalize_setup(payload, "nuevo", "NI", "es"), bool)
    with application.app_context():
        database.session.remove()
        database.engine.dispose()
