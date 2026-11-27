# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El alta de bancos y cuentas bancarias valida referencias y longitudes.

Escenarios de negocio (#2088, #2086, #2087, #2028, #2029): una cuenta bancaria
exige una cuenta GL de banco activa, habilitada y hoja de la propia compañía, un
banco activo y textos dentro del límite de columna; un banco exige nombre
obligatorio y SWIFT de hasta 20 caracteres. Todo rechazo es controlado y no deja
filas persistidas.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Accounts, Bank, BankAccount, database

MARKER_FORMULARIO_CUENTA = (
    "La Plantilla fue renderizada correctamente: cacao_accounting/bancos/templates/bancos/banco_cuenta_nuevo.html"
)
MARKER_FORMULARIO_BANCO = (
    "La Plantilla fue renderizada correctamente: cacao_accounting/bancos/templates/bancos/banco_nuevo.html"
)
MENSAJE_CUENTA_GL = "Seleccione una cuenta contable de tipo banco, activa y habilitada, para la compañía indicada."


def _crear_banco(sufijo: str, activo: bool = True) -> str:
    """Crea un banco con el estado solicitado y devuelve su id."""
    banco = Bank(name=f"Banco forma {sufijo}", is_active=activo)
    database.session.add(banco)
    database.session.flush()
    return str(banco.id)


def _crear_cuenta_gl_banco(sufijo: str, entidad: str = "cacao", **banderas) -> str:
    """Crea una cuenta contable de tipo banco con las banderas indicadas."""
    cuenta = Accounts(
        entity=entidad,
        code=f"1102-{sufijo}",
        name=f"Bancos forma {sufijo}",
        classification="asset",
        account_type="bank",
        currency="NIO",
        **banderas,
    )
    database.session.add(cuenta)
    database.session.flush()
    return str(cuenta.id)


def _enviar_cuenta_bancaria(authenticated_client, banco_id: str, **extras) -> object:
    """POSTea el formulario de cuenta bancaria con valores base y extras."""
    sufijo = uuid4().hex[:8]
    datos = {
        "bank_id": banco_id,
        "company": "cacao",
        "account_name": f"Cuenta forma {sufijo}",
        "account_no": f"FB-{sufijo}",
        "iban": "",
        "currency": "NIO",
        "gl_account_id": "",
    }
    datos.update(extras)
    return authenticated_client("admin").post("/cash_management/bank-account/new", data=datos)


def test_cuenta_bancaria_rechaza_cuenta_gl_inactiva(app, entorno_contable, authenticated_client):
    """El formulario no crea la cuenta cuando la cuenta GL está inactiva (#2088)."""
    with app.app_context():
        sufijo = uuid4().hex[:8]
        gl_id = _crear_cuenta_gl_banco(sufijo, active=False, enabled=True, group=False)
        banco_id = _crear_banco(sufijo)
        database.session.commit()
        filas_antes = database.session.query(BankAccount).count()

    response = _enviar_cuenta_bancaria(authenticated_client, banco_id, gl_account_id=gl_id)

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert MARKER_FORMULARIO_CUENTA in cuerpo
    with app.app_context():
        assert database.session.query(BankAccount).count() == filas_antes


def test_cuenta_bancaria_rechaza_cuenta_gl_agrupadora(app, entorno_contable, authenticated_client):
    """Una cuenta GL agrupadora tampoco puede respaldar una cuenta bancaria (#2088)."""
    with app.app_context():
        sufijo = uuid4().hex[:8]
        gl_id = _crear_cuenta_gl_banco(sufijo, active=True, enabled=True, group=True)
        banco_id = _crear_banco(sufijo)
        database.session.commit()
        filas_antes = database.session.query(BankAccount).count()

    response = _enviar_cuenta_bancaria(authenticated_client, banco_id, gl_account_id=gl_id)

    assert response.status_code == 200
    assert MARKER_FORMULARIO_CUENTA in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.query(BankAccount).count() == filas_antes


def test_cuenta_bancaria_rechaza_cuenta_gl_de_otra_compania(app, entorno_contable, authenticated_client):
    """La guardia de servicio flasha el error cuando la cuenta GL pertenece a otra compañía (#2088)."""
    with app.app_context():
        sufijo = uuid4().hex[:8]
        gl_id = _crear_cuenta_gl_banco(sufijo, entidad="alpha", active=True, enabled=True, group=False)
        banco_id = _crear_banco(sufijo)
        database.session.commit()
        filas_antes = database.session.query(BankAccount).count()

    response = _enviar_cuenta_bancaria(authenticated_client, banco_id, gl_account_id=gl_id)

    assert response.status_code == 200
    assert MENSAJE_CUENTA_GL in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.query(BankAccount).count() == filas_antes


def test_cuenta_bancaria_acepta_cuenta_gl_de_banco_activa(app, entorno_contable, authenticated_client):
    """Control positivo: con cuenta GL de banco operativa el alta procede (#2088)."""
    with app.app_context():
        sufijo = uuid4().hex[:8]
        gl_id = _crear_cuenta_gl_banco(sufijo, active=True, enabled=True, group=False)
        banco_id = _crear_banco(sufijo)
        database.session.commit()

    response = _enviar_cuenta_bancaria(authenticated_client, banco_id, gl_account_id=gl_id)

    assert response.status_code == 302
    with app.app_context():
        cuenta = database.session.query(BankAccount).filter_by(gl_account_id=gl_id).one()
        assert cuenta.company == "cacao"
        assert cuenta.bank_id == banco_id


def test_cuenta_bancaria_rechaza_banco_inactivo(app, entorno_contable, authenticated_client):
    """Un banco desactivado no puede respaldar nuevas cuentas bancarias (#2086)."""
    with app.app_context():
        sufijo = uuid4().hex[:8]
        banco_id = _crear_banco(sufijo, activo=False)
        database.session.commit()
        filas_antes = database.session.query(BankAccount).count()

    response = _enviar_cuenta_bancaria(authenticated_client, banco_id)

    assert response.status_code == 200
    assert MARKER_FORMULARIO_CUENTA in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.query(BankAccount).count() == filas_antes


def test_cuenta_bancaria_acepta_banco_activo(app, entorno_contable, authenticated_client):
    """Control positivo: el banco activo permite crear la cuenta bancaria (#2086)."""
    with app.app_context():
        sufijo = uuid4().hex[:8]
        banco_id = _crear_banco(sufijo)
        database.session.commit()

    response = _enviar_cuenta_bancaria(authenticated_client, banco_id)

    assert response.status_code == 302
    with app.app_context():
        cuenta = database.session.query(BankAccount).filter_by(bank_id=banco_id).one()
        assert cuenta.company == "cacao"
        assert cuenta.account_no


@pytest.mark.parametrize(
    "campo,longitud,mensaje",
    [
        ("account_name", 151, "El nombre de la cuenta no puede superar los 150 caracteres."),
        ("account_no", 51, "El número de cuenta no puede superar los 50 caracteres."),
        ("iban", 51, "El IBAN no puede superar los 50 caracteres."),
    ],
)
def test_cuenta_bancaria_rechaza_textos_excesivos(app, entorno_contable, authenticated_client, campo, longitud, mensaje):
    """Los textos sobre el límite de columna se rechazan como error de formulario (#2087)."""
    with app.app_context():
        sufijo = uuid4().hex[:8]
        banco_id = _crear_banco(sufijo)
        database.session.commit()
        filas_antes = database.session.query(BankAccount).count()

    response = _enviar_cuenta_bancaria(authenticated_client, banco_id, **{campo: "V" * longitud})

    assert response.status_code == 200
    assert mensaje in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.query(BankAccount).count() == filas_antes


def test_cuenta_bancaria_acepta_textos_en_el_limite_exacto(app, entorno_contable, authenticated_client):
    """Control positivo: 150/50/50 caracteres son longitudes válidas (#2087)."""
    with app.app_context():
        sufijo = uuid4().hex[:8]
        banco_id = _crear_banco(sufijo)
        database.session.commit()
    nombre = (f"Cuenta límite {sufijo} " + "x" * 200)[:150]
    numero = (f"FB-{sufijo}-" + "9" * 100)[:50]

    response = _enviar_cuenta_bancaria(authenticated_client, banco_id, account_name=nombre, account_no=numero, iban=numero)

    assert response.status_code == 302
    with app.app_context():
        cuenta = database.session.query(BankAccount).filter_by(account_no=numero).one()
        assert len(cuenta.account_name) == 150
        assert len(cuenta.iban) == 50


def test_banco_rechaza_swift_code_excesivo(app, entorno_contable, authenticated_client):
    """Un SWIFT de 21 caracteres se rechaza como error de campo sin crear el banco (#2028)."""
    sufijo = uuid4().hex[:8]
    with app.app_context():
        filas_antes = database.session.query(Bank).count()

    response = authenticated_client("admin").post(
        "/cash_management/bank/new", data={"name": f"Banco swift {sufijo}", "swift_code": "A" * 21}
    )

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "El código SWIFT no puede superar los 20 caracteres." in cuerpo
    assert MARKER_FORMULARIO_BANCO in cuerpo
    with app.app_context():
        assert database.session.query(Bank).count() == filas_antes


def test_banco_acepta_swift_code_de_20(app, entorno_contable, authenticated_client):
    """Control positivo: un SWIFT de 20 caracteres crea el banco (#2028)."""
    sufijo = uuid4().hex[:8]
    nombre = f"Banco swift {sufijo}"

    response = authenticated_client("admin").post("/cash_management/bank/new", data={"name": nombre, "swift_code": "B" * 20})

    assert response.status_code == 302
    with app.app_context():
        banco = database.session.query(Bank).filter_by(name=nombre).one()
        assert len(banco.swift_code) == 20
        assert banco.is_active


def test_banco_rechaza_nombre_vacio(app, entorno_contable, authenticated_client):
    """El nombre vacío re-renderiza el formulario mostrando el error de campo (#2029)."""
    with app.app_context():
        filas_antes = database.session.query(Bank).count()

    response = authenticated_client("admin").post("/cash_management/bank/new", data={"name": "", "swift_code": ""})

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Este campo es obligatorio." in cuerpo
    assert MARKER_FORMULARIO_BANCO in cuerpo
    with app.app_context():
        assert database.session.query(Bank).count() == filas_antes
