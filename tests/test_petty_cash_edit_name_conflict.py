# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1646: el conflicto concurrente de nombre se traduce sin ocultar otros errores."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from cacao_accounting import create_app
from cacao_accounting.bancos import services as bank_services
from cacao_accounting.bancos.services import update_petty_cash_account
from cacao_accounting.config import configuracion
from cacao_accounting.database import Accounts, Currency, Entity, PettyCashAccount, database


def _fondo(company: str, account_id: str, name: str) -> PettyCashAccount:
    fondo = PettyCashAccount(
        company=company,
        account_id=account_id,
        name=name,
        currency="NIO",
        float_amount=Decimal("100"),
        is_default=False,
        is_active=True,
    )
    database.session.add(fondo)
    database.session.flush()
    return fondo


def _database_app(tmp_path):
    """Crea una app contra SQLite temporal o el motor externo habilitado por CI."""
    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        uri = f"sqlite:///{tmp_path / 'petty-cash-name.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {
                **configuracion.get("SQLALCHEMY_ENGINE_OPTIONS", {}),
                "pool_size": 4,
                "max_overflow": 0,
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test-petty-cash-name",
            "MODO_ESCRITORIO": False,
        }
    )


@pytest.fixture
def cuentas_caja_chica(app, entorno_contable):
    """Crea cuentas GL petty_cash NIO/USD y un fondo NIO para #1088."""
    del entorno_contable
    sufijo = uuid4().hex[:8]
    with app.app_context():
        cuenta_nio = Accounts(
            entity="cacao",
            code=f"1088-NIO-{sufijo}",
            name="Caja chica NIO",
            account_type="petty_cash",
            currency="NIO",
            active=True,
            enabled=True,
            group=False,
        )
        otra_nio = Accounts(
            entity="cacao",
            code=f"1088-NIO2-{sufijo}",
            name="Caja chica NIO alternativa",
            account_type="petty_cash",
            currency="NIO",
            active=True,
            enabled=True,
            group=False,
        )
        cuenta_usd = Accounts(
            entity="cacao",
            code=f"1088-USD-{sufijo}",
            name="Caja chica USD",
            account_type="petty_cash",
            currency="USD",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add_all([cuenta_nio, otra_nio, cuenta_usd])
        database.session.flush()
        fondo = _fondo("cacao", cuenta_nio.id, f"Caja moneda {sufijo}")
        database.session.commit()
        ids = {
            "fondo": fondo.id,
            "nio": cuenta_nio.id,
            "otra_nio": otra_nio.id,
            "usd": cuenta_usd.id,
            "cuentas": [cuenta_nio.id, otra_nio.id, cuenta_usd.id],
        }
    yield ids
    with app.app_context():
        database.session.execute(database.delete(PettyCashAccount).where(PettyCashAccount.id == ids["fondo"]))
        database.session.execute(database.delete(Accounts).where(Accounts.id.in_(ids["cuentas"])))
        database.session.commit()


def test_cuenta_petty_cash_compatible_se_guarda_sin_cambiar_moneda(app, cuentas_caja_chica):
    """#1088: otra cuenta NIO actualiza el fondo y conserva su moneda."""
    with app.app_context():
        fondo = database.session.get(PettyCashAccount, cuentas_caja_chica["fondo"])
        assert fondo is not None

        actualizado = update_petty_cash_account(
            fondo,
            account_id=cuentas_caja_chica["otra_nio"],
            float_amount=Decimal("250"),
        )

        database.session.refresh(actualizado)
        assert actualizado.account_id == cuentas_caja_chica["otra_nio"]
        assert actualizado.currency == "NIO"
        assert actualizado.float_amount == Decimal("250")


@pytest.mark.parametrize("currency", [None, "NIO"], ids=["sin-moneda", "moneda-explicita"])
def test_cuenta_usd_incompatible_no_muta_y_permite_reutilizar_sesion(app, cuentas_caja_chica, currency):
    """#1088: el mismatch deja ORM y sesión limpios, incluso con otros cambios."""
    with app.app_context():
        fondo = database.session.get(PettyCashAccount, cuentas_caja_chica["fondo"])
        assert fondo is not None
        original = (fondo.name, fondo.account_id, fondo.currency, fondo.float_amount, fondo.notes)
        cambios = {
            "name": "Nombre que no debe aplicarse",
            "account_id": cuentas_caja_chica["usd"],
            "float_amount": Decimal("999"),
            "notes": "Nota que no debe aplicarse",
        }
        if currency is not None:
            cambios["currency"] = currency

        with pytest.raises(ValueError, match="La moneda de la caja chica debe coincidir"):
            update_petty_cash_account(fondo, **cambios)

        assert (fondo.name, fondo.account_id, fondo.currency, fondo.float_amount, fondo.notes) == original
        assert fondo not in database.session.dirty
        assert not database.session.is_modified(fondo)
        assert database.session.is_active

        recuperado = update_petty_cash_account(fondo, notes="Sesión reutilizada")
        database.session.refresh(recuperado)
        assert recuperado.notes == "Sesión reutilizada"
        assert recuperado.account_id == original[1]
        assert recuperado.currency == "NIO"


def test_conflicto_de_unicidad_se_traduce_y_libera_la_sesion(app, entorno_contable, monkeypatch):
    """La carrera que supera el prechequeo recibe ValueError y permite reintentar."""
    del entorno_contable
    sufijo = uuid4().hex[:8]
    with app.app_context():
        cuenta = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        existente = _fondo("cacao", cuenta.id, f"Caja existente {sufijo}")
        a_renombrar = _fondo("cacao", cuenta.id, f"Caja a renombrar {sufijo}")
        database.session.commit()
        existente_id, a_renombrar_id = existente.id, a_renombrar.id

        monkeypatch.setattr(bank_services, "_petty_cash_name_exists", lambda *args, **kwargs: False)

        with pytest.raises(ValueError, match="Ya existe una caja chica con ese nombre"):
            update_petty_cash_account(
                database.session.get(PettyCashAccount, a_renombrar_id),
                name=f"Caja existente {sufijo}",
            )

        actualizado = update_petty_cash_account(
            database.session.get(PettyCashAccount, a_renombrar_id),
            name=f"Caja recuperada {sufijo}",
        )
        assert actualizado.name == f"Caja recuperada {sufijo}"

        database.session.execute(
            database.delete(PettyCashAccount).where(PettyCashAccount.id.in_([existente_id, a_renombrar_id]))
        )
        database.session.commit()


def test_conflicto_con_formulario_completo_se_traduce(app, cuentas_caja_chica, monkeypatch):
    """Cuenta, moneda y notas no dejan el flush del nombre fuera de la protección."""
    with app.app_context():
        existente = _fondo("cacao", cuentas_caja_chica["nio"], "Caja duplicada completa")
        database.session.commit()
        existente_id = existente.id
        fondo_id = cuentas_caja_chica["fondo"]
        original = database.session.get(PettyCashAccount, fondo_id).name
        monkeypatch.setattr(bank_services, "_petty_cash_name_exists", lambda *args, **kwargs: False)

        try:
            with pytest.raises(ValueError, match="Ya existe una caja chica con ese nombre"):
                update_petty_cash_account(
                    database.session.get(PettyCashAccount, fondo_id),
                    name="Caja duplicada completa",
                    account_id=cuentas_caja_chica["nio"],
                    currency="NIO",
                    notes="No debe persistir",
                )

            assert database.session.is_active
            recuperado = update_petty_cash_account(
                database.session.get(PettyCashAccount, fondo_id),
                notes="Sesión recuperada",
            )
            assert recuperado.name == original
            assert recuperado.notes == "Sesión recuperada"
        finally:
            database.session.execute(database.delete(PettyCashAccount).where(PettyCashAccount.id == existente_id))
            database.session.commit()


def test_http_conflicto_de_nombre_devuelve_error_controlado(app, authenticated_client, cuentas_caja_chica, monkeypatch):
    """La ruta real con formulario completo no convierte la colisión en HTTP 500."""
    with app.app_context():
        existente = _fondo("cacao", cuentas_caja_chica["nio"], "Caja duplicada HTTP")
        database.session.commit()
        existente_id = existente.id
        fondo_id = cuentas_caja_chica["fondo"]
        original = database.session.get(PettyCashAccount, fondo_id).name

    monkeypatch.setattr(bank_services, "_petty_cash_name_exists", lambda *args, **kwargs: False)
    try:
        response = authenticated_client("admin").post(
            f"/cash_management/petty-cash/{fondo_id}/edit",
            data={
                "name": "Caja duplicada HTTP",
                "account_id": cuentas_caja_chica["nio"],
                "currency": "NIO",
                "float_amount": "250",
                "notes": "No debe persistir",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "Ya existe una caja chica con ese nombre" in response.get_data(as_text=True)
        with app.app_context():
            fondo = database.session.get(PettyCashAccount, fondo_id)
            assert fondo.name == original
            assert fondo.notes != "No debe persistir"
    finally:
        with app.app_context():
            database.session.execute(database.delete(PettyCashAccount).where(PettyCashAccount.id == existente_id))
            database.session.commit()


@pytest.mark.database
def test_dos_sesiones_concurrentes_dejan_un_nombre_y_un_conflicto(tmp_path, monkeypatch):
    """Dos escrituras reales superan el prechequeo y solo una confirma el nombre."""
    app = _database_app(tmp_path)
    suffix = uuid4().hex[:8]
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                ),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
            ]
        )
        database.session.flush()
        account = Accounts(
            entity="cacao",
            code="1101",
            name="Caja",
            classification="asset",
            account_type="petty_cash",
            currency="NIO",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add(account)
        database.session.flush()
        primero = _fondo("cacao", account.id, f"Primero {suffix}")
        segundo = _fondo("cacao", account.id, f"Segundo {suffix}")
        database.session.commit()
        ids = (primero.id, segundo.id)
        account_id = account.id
        database.session.remove()

    barrier = Barrier(2, timeout=30)

    def pasar_prechequeo(*_args, **_kwargs):
        barrier.wait(timeout=10)
        return False

    monkeypatch.setattr(bank_services, "_petty_cash_name_exists", pasar_prechequeo)

    def renombrar(fondo_id: str) -> str:
        with app.app_context():
            try:
                update_petty_cash_account(
                    database.session.get(PettyCashAccount, fondo_id),
                    name="Caja concurrente",
                    account_id=account_id,
                    currency="NIO",
                    notes="Concurrencia real",
                )
            except ValueError as exc:
                if "Ya existe una caja chica con ese nombre" not in str(exc):
                    raise
                return "conflicto"
            return "exito"

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            resultados = list(workers.map(renombrar, ids))
        assert sorted(resultados) == ["conflicto", "exito"]
        with app.app_context():
            fondos = (
                database.session.execute(database.select(PettyCashAccount).where(PettyCashAccount.id.in_(ids))).scalars().all()
            )
            assert sum(fondo.name == "Caja concurrente" for fondo in fondos) == 1
            assert {fondo.name for fondo in fondos} <= {"Caja concurrente", f"Primero {suffix}", f"Segundo {suffix}"}
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_error_de_integridad_ajeno_no_se_confunde_con_duplicado():
    """Una violación de FK no se presenta como nombre duplicado."""
    error = IntegrityError("INSERT", {}, Exception("FOREIGN KEY constraint failed"))

    assert bank_services._is_petty_cash_name_conflict(error) is False
    assert bank_services._is_petty_cash_name_conflict(
        IntegrityError(
            "INSERT", {}, Exception("UNIQUE constraint failed: petty_cash_account.company, petty_cash_account.name")
        )
    )
    assert (
        bank_services._is_petty_cash_name_conflict(
            IntegrityError(
                "INSERT",
                {},
                Exception('duplicate key value violates unique constraint "uq_petty_cash_account_default_company"'),
            )
        )
        is False
    )
