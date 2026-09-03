# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas para Caja Chica (Petty Cash)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    """Aplicacion aislada con datos minimos para caja chica."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Currency, Entity, Modules, database

        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Cordobas", decimals=2, active=True, default=True),
                Currency(code="USD", name="Dolares", decimals=2, active=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO"),
                Modules(module="cash", default=False, enabled=True),
            ]
        )
        database.session.commit()
        yield app
        database.session.remove()
        database.drop_all()


def _crear_cuenta_petty_cash(company: str = "cacao") -> object:
    """Crea una cuenta contable de tipo petty_cash para la compania."""
    from cacao_accounting.database import Accounts, database

    cuenta = Accounts(
        entity=company,
        code="1105",
        name="Caja Chica",
        active=True,
        enabled=True,
        group=False,
        account_type="petty_cash",
    )
    database.session.add(cuenta)
    database.session.commit()
    return cuenta


def _crear_cuenta_cash(company: str = "cacao") -> object:
    """Crea una cuenta contable de tipo cash para la compania."""
    from cacao_accounting.database import Accounts, database

    cuenta = Accounts(
        entity=company,
        code="1101",
        name="Caja General",
        active=True,
        enabled=True,
        group=False,
        account_type="cash",
    )
    database.session.add(cuenta)
    database.session.commit()
    return cuenta


def _crear_usuario_admin(username: str = "cajera") -> object:
    """Crea un usuario con clasificacion admin (respeta el modulo activo)."""
    from cacao_accounting.database import User, database

    usuario = User(user=username, name=username.title(), classification="admin", active=True, password=b"password")
    database.session.add(usuario)
    database.session.commit()
    return usuario


# -------------------------------------------------------------------------------------
# Catalogos y tipo de cuenta
# -------------------------------------------------------------------------------------
def test_petty_cash_en_especiales(app_ctx):
    """El tipo de cuenta petty_cash esta incluido en los tipos especiales."""
    from cacao_accounting.contabilidad.default_accounts import SPECIAL_ACCOUNT_TYPES, ACCOUNT_TYPE_ALLOWED_VOUCHERS

    assert "petty_cash" in SPECIAL_ACCOUNT_TYPES
    assert "petty_cash" in ACCOUNT_TYPE_ALLOWED_VOUCHERS
    assert "journal_entry" in ACCOUNT_TYPE_ALLOWED_VOUCHERS["petty_cash"]


def test_petty_cash_en_choices_de_forms(app_ctx):
    """El tipo petty_cash esta disponible en el selector de tipos de cuenta."""
    from cacao_accounting.contabilidad.forms import ACCOUNT_TYPE_CHOICES

    choices = [code for code, _ in ACCOUNT_TYPE_CHOICES]
    assert "petty_cash" in choices


def test_petty_cash_en_flujo_de_efectivo(app_ctx):
    """El tipo petty_cash se clasifica como efectivo en el estado de flujos."""
    from cacao_accounting.reportes.cash_flow import _SUGGESTION_BY_ACCOUNT_TYPE, SECTION_CASH

    assert _SUGGESTION_BY_ACCOUNT_TYPE.get("petty_cash") is SECTION_CASH


def test_petty_cash_en_tipos_monetarios(app_ctx):
    """El tipo petty_cash se considera monetario para la revaluacion cambiaria."""
    from cacao_accounting.contabilidad.exchange_revaluation_service import MONETARY_ACCOUNT_TYPES

    assert "petty_cash" in MONETARY_ACCOUNT_TYPES


def test_catalogos_retipan_petty_cash():
    """Las cuentas de efectivo chico de los catalogos CSV se re-tiparon a petty_cash."""
    import csv
    from os import listdir
    from os.path import join

    from cacao_accounting.contabilidad.ctas import DIRECTORIO_CTAS

    archivos = sorted(f for f in listdir(DIRECTORIO_CTAS) if f.endswith(".csv"))
    assert archivos, "No se encontraron catalogos CSV."
    for archivo in archivos:
        with open(join(DIRECTORIO_CTAS, archivo), "r", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        tipos = {str(row.get("account_type") or row.get("tipo_cuenta") or "").strip() for row in rows}
        assert "petty_cash" in tipos


# -------------------------------------------------------------------------------------
# Servicios
# -------------------------------------------------------------------------------------
def test_crear_caja_chica(app_ctx):
    """Se puede crear una caja chica con cuenta contable y responsable validos."""
    from cacao_accounting.bancos.services import create_petty_cash_account

    cuenta = _crear_cuenta_petty_cash()
    responsable = _crear_usuario_admin()
    caja = create_petty_cash_account(
        company="cacao",
        account_id=str(cuenta.id),
        name="Caja Chica Principal",
        currency="NIO",
        custodian_id=str(responsable.id),
        float_amount=Decimal("100.0000"),
    )
    assert caja.id is not None
    assert caja.name == "Caja Chica Principal"
    assert caja.float_amount == Decimal("100.0000")


def test_crear_caja_chica_sin_nombre_falla(app_ctx):
    """No se puede crear una caja chica sin nombre."""
    from cacao_accounting.bancos.services import create_petty_cash_account

    cuenta = _crear_cuenta_petty_cash()
    with pytest.raises(ValueError):
        create_petty_cash_account(
            company="cacao",
            account_id=str(cuenta.id),
            name="   ",
            currency="NIO",
            custodian_id=None,
        )


def test_crear_caja_chica_fondo_negativo_falla(app_ctx):
    """No se puede crear una caja chica con fondo autorizado negativo."""
    from cacao_accounting.bancos.services import create_petty_cash_account

    cuenta = _crear_cuenta_petty_cash()
    with pytest.raises(ValueError):
        create_petty_cash_account(
            company="cacao",
            account_id=str(cuenta.id),
            name="Caja A",
            currency="NIO",
            custodian_id=None,
            float_amount=Decimal("-1"),
        )


def test_crear_caja_chica_cuenta_incorrecta_falla(app_ctx):
    """La cuenta contable debe existir y ser de tipo petty_cash."""
    from cacao_accounting.bancos.services import create_petty_cash_account

    cuenta_cash = _crear_cuenta_cash()
    with pytest.raises(ValueError):
        create_petty_cash_account(
            company="cacao",
            account_id=str(cuenta_cash.id),
            name="Caja B",
            currency="NIO",
            custodian_id=None,
        )


def test_crear_caja_chica_cuenta_inexistente_falla(app_ctx):
    """No se puede usar una cuenta contable inexistente."""
    from cacao_accounting.bancos.services import create_petty_cash_account

    with pytest.raises(ValueError):
        create_petty_cash_account(
            company="cacao",
            account_id="no-existe",
            name="Caja C",
            currency="NIO",
            custodian_id=None,
        )


def test_custodio_sin_acceso_falla(app_ctx):
    """El responsable debe tener acceso al modulo de caja y bancos."""
    from cacao_accounting.bancos.services import create_petty_cash_account
    from cacao_accounting.database import User, database

    cuenta = _crear_cuenta_petty_cash()
    sin_acceso = User(user="sinacceso", name="Sin Acceso", classification="user", active=True, password=b"password")
    database.session.add(sin_acceso)
    database.session.commit()
    with pytest.raises(ValueError):
        create_petty_cash_account(
            company="cacao",
            account_id=str(cuenta.id),
            name="Caja D",
            currency="NIO",
            custodian_id=str(sin_acceso.id),
        )


def test_crear_caja_chica_duplicada_falla(app_ctx):
    """No se pueden crear dos cajas chicas con el mismo nombre en la compania."""
    from cacao_accounting.bancos.services import create_petty_cash_account

    cuenta = _crear_cuenta_petty_cash()
    create_petty_cash_account(
        company="cacao",
        account_id=str(cuenta.id),
        name="Caja Unica",
        currency="NIO",
        custodian_id=None,
    )
    with pytest.raises(ValueError):
        create_petty_cash_account(
            company="cacao",
            account_id=str(cuenta.id),
            name="Caja Unica",
            currency="NIO",
            custodian_id=None,
        )


def test_predeterminada_unica_por_compania(app_ctx):
    """Marcar una caja como predeterminada limpia la marca de las demas."""
    from cacao_accounting.bancos.services import create_petty_cash_account, set_petty_cash_default
    from cacao_accounting.database import database

    cuenta = _crear_cuenta_petty_cash()
    caja_a = create_petty_cash_account(
        company="cacao",
        account_id=str(cuenta.id),
        name="Caja A",
        currency="NIO",
        custodian_id=None,
        is_default=True,
    )
    caja_b = create_petty_cash_account(
        company="cacao",
        account_id=str(cuenta.id),
        name="Caja B",
        currency="NIO",
        custodian_id=None,
    )
    assert caja_a.is_default is True
    assert caja_b.is_default is False
    set_petty_cash_default(caja_b)
    database.session.refresh(caja_a)
    assert caja_a.is_default is False
    assert caja_b.is_default is True


def test_alternar_estado(app_ctx):
    """Alternar el estado activo/inactivo no borra el registro (append-only)."""
    from cacao_accounting.bancos.services import create_petty_cash_account, toggle_petty_cash_active

    cuenta = _crear_cuenta_petty_cash()
    caja = create_petty_cash_account(
        company="cacao",
        account_id=str(cuenta.id),
        name="Caja E",
        currency="NIO",
        custodian_id=None,
    )
    assert caja.is_active is True
    toggle_petty_cash_active(caja)
    assert caja.is_active is False
    assert caja.id is not None


def test_saldo_contable_desde_gl(app_ctx):
    """El saldo contable se deriva del GL sumando (debit - credit)."""
    from cacao_accounting.bancos.services import create_petty_cash_account, petty_cash_ledger_balance
    from cacao_accounting.database import GLEntry, database

    cuenta = _crear_cuenta_petty_cash()
    caja = create_petty_cash_account(
        company="cacao",
        account_id=str(cuenta.id),
        name="Caja F",
        currency="NIO",
        custodian_id=None,
    )
    database.session.add_all(
        [
            GLEntry(
                posting_date=date(2026, 1, 1),
                company="cacao",
                account_id=str(cuenta.id),
                debit=Decimal("500.0000"),
                credit=Decimal("0"),
                voucher_type="journal_entry",
                voucher_id="V-1",
            ),
            GLEntry(
                posting_date=date(2026, 1, 2),
                company="cacao",
                account_id=str(cuenta.id),
                debit=Decimal("0"),
                credit=Decimal("100.0000"),
                voucher_type="journal_entry",
                voucher_id="V-2",
            ),
        ]
    )
    database.session.commit()
    assert petty_cash_ledger_balance(caja) == Decimal("400.0000")


def test_saldo_contable_sin_registros_es_cero(app_ctx):
    """Sin asientos, el saldo contable es cero."""
    from cacao_accounting.bancos.services import create_petty_cash_account, petty_cash_ledger_balance

    cuenta = _crear_cuenta_petty_cash()
    caja = create_petty_cash_account(
        company="cacao",
        account_id=str(cuenta.id),
        name="Caja G",
        currency="NIO",
        custodian_id=None,
    )
    assert petty_cash_ledger_balance(caja) == Decimal("0")


def test_listar_cajas_chicas(app_ctx):
    """La lista de cajas chicas devuelve las de la compania."""
    from cacao_accounting.bancos.services import create_petty_cash_account, petty_cash_accounts

    cuenta = _crear_cuenta_petty_cash()
    create_petty_cash_account(
        company="cacao",
        account_id=str(cuenta.id),
        name="Caja H",
        currency="NIO",
        custodian_id=None,
    )
    cajas = petty_cash_accounts("cacao")
    assert len(cajas) == 1
    assert cajas[0].name == "Caja H"


# -------------------------------------------------------------------------------------
# Setup
# -------------------------------------------------------------------------------------
def test_create_default_petty_cash_idempotente(app_ctx):
    """El setup crea una caja chica predeterminada; repetir no crea duplicados."""
    from cacao_accounting.bancos.services import create_default_petty_cash, petty_cash_accounts
    from cacao_accounting.database import User, database

    _crear_cuenta_petty_cash()
    admin_fallback = User(user="admin", name="Admin", classification="admin", active=True, password=b"password")
    database.session.add(admin_fallback)
    database.session.commit()

    primera = create_default_petty_cash("cacao", custodian_id=str(admin_fallback.id))
    segunda = create_default_petty_cash("cacao", custodian_id=str(admin_fallback.id))
    assert primera is not None
    assert segunda.id == primera.id
    assert len(petty_cash_accounts("cacao")) == 1
    assert primera.is_default is True


def test_create_default_petty_cash_sin_cuenta_devuelve_none(app_ctx):
    """Si el catalogo no tiene cuenta petty_cash, no se crea ninguna caja."""
    from cacao_accounting.bancos.services import create_default_petty_cash

    _crear_cuenta_cash()
    assert create_default_petty_cash("cacao") is None


def test_create_default_selecciona_minima_cuenta(app_ctx):
    """La caja predeterminada se asocia a la primera cuenta petty_cash por codigo."""
    from cacao_accounting.bancos.services import create_default_petty_cash
    from cacao_accounting.database import Accounts, User, database

    _crear_cuenta_petty_cash()
    segunda = Accounts(
        entity="cacao", code="1106", name="Caja Chica 2", active=True, enabled=True, group=False, account_type="petty_cash"
    )
    database.session.add(segunda)
    admin_fallback = User(user="admin2", name="Admin2", classification="admin", active=True, password=b"password")
    database.session.add(admin_fallback)
    database.session.commit()
    caja = create_default_petty_cash("cacao", custodian_id=str(admin_fallback.id))
    assert caja is not None
    cuenta = database.session.get(Accounts, caja.account_id)
    assert cuenta.code == "1105"


@pytest.fixture()
def app_ctx_full():
    """Aplicacion con datos base (modulos, usuarios, roles) para pruebas web."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Accounts, Currency, database
        from cacao_accounting.database.helpers import inicia_base_de_datos

        inicia_base_de_datos(app, user="cacao", passwd="cacao", with_examples=False)
        if not database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none():
            database.session.add(Currency(code="NIO", name="Cordobas", decimals=2, active=True, default=True))
        if (
            not database.session.execute(database.select(Accounts).filter_by(entity="cacao", account_type="petty_cash"))
            .scalars()
            .first()
        ):
            database.session.add(
                Accounts(
                    entity="cacao",
                    code="11.01.001.003",
                    name="Caja Chica",
                    active=True,
                    enabled=True,
                    group=False,
                    account_type="petty_cash",
                )
            )
        database.session.commit()
        yield app
        database.session.remove()
        database.drop_all()


def _login(client, username: str = "cacao", password: str = "cacao"):
    """Inicia sesion con el cliente de pruebas."""
    return client.post("/login", data={"usuario": username, "acceso": password}, follow_redirects=True)


# -------------------------------------------------------------------------------------
# Rutas
# -------------------------------------------------------------------------------------
def test_crear_caja_chica_via_web(app_ctx_full):
    """El POST autenticado de creacion crea la caja chica y redirige al listado."""
    from cacao_accounting.database import Accounts, database

    cuenta = (
        database.session.execute(
            database.select(Accounts).filter_by(entity="cacao", account_type="petty_cash").order_by(Accounts.code)
        )
        .scalars()
        .first()
    )
    assert cuenta is not None, "El catalogo base debe incluir una cuenta petty_cash."
    client = app_ctx_full.test_client()
    _login(client)
    resp = client.post(
        "/cash_management/petty-cash/new",
        data={
            "company": "cacao",
            "name": "Caja Chica Web",
            "account_id": str(cuenta.id),
            "currency": "NIO",
            "custodian_id": "",
            "float_amount": "50",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    from cacao_accounting.bancos.services import petty_cash_accounts

    assert any(caja.name == "Caja Chica Web" for caja in petty_cash_accounts("cacao"))
