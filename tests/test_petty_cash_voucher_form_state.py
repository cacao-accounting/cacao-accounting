# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Rehidratación del formulario de vales al fallar el POST (#2035).

Escenario de negocio: una cajera selecciona compañía, fondo y centro de costo,
pero el importe o el concepto del vale son inválidos. El sistema rechaza el
POST sin perder su trabajo: re-renderiza el formulario con los selectores
rehidratados vía ``_voucher_form_state`` (compañía, fondo, moneda y
dimensiones) y ningún vale persistido.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Book,
    CostCenter,
    Currency,
    Entity,
    Modules,
    PettyCashAccount,
    PettyCashVoucher,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "caja-vale-estado-2026"
FECHA = date(2026, 11, 12)


@pytest.fixture
def caja_vale_estado():
    """Compañía con fondo y centro de costo para el formulario de vales."""
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
                User(
                    id="cajera-vales",
                    user="cajera-vales",
                    name="Cajera de Vales",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add(
            Book(
                entity="cacao",
                code="DEFAULT_BOOK",
                name="Libro principal",
                status="activo",
                currency="NIO",
                is_primary=True,
            )
        )
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id="cajera-vales", company_code="cacao"))
        database.session.flush()
        rol_creador = Roles(name="cash-crea-vales", note="Crea vales de caja chica")
        database.session.add(rol_creador)
        database.session.flush()
        modulo_caja = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one()
        database.session.add(RolesAccess(rol_id=rol_creador.id, module_id=modulo_caja.id, access=True, create=True, view=True))
        database.session.add(RolesUser(user_id="cajera-vales", role_id=rol_creador.id, active=True))
        database.session.flush()
        cuenta = Accounts(
            code="1.01.05.001",
            name="Caja Chica Vales",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="petty_cash",
        )
        centro = CostCenter(code="CC-VALES", name="Centro Vales", entity="cacao", active=True, enabled=True, group=False)
        database.session.add_all([cuenta, centro])
        database.session.flush()
        fondo = PettyCashAccount(
            company="cacao",
            account_id=cuenta.id,
            name="Fondo Vales Rehidratados",
            currency="NIO",
            float_amount=Decimal("1000"),
            is_default=True,
            is_active=True,
        )
        database.session.add(fondo)
        database.session.commit()
        ids = {"fondo": fondo.id, "centro": centro.code}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "cajera-vales", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def _postear_vale(client, ids, **reemplazos):
    """POSTea un vale de caja chica con valores válidos y reemplazos opcionales."""
    datos = {
        "company": "cacao",
        "petty_cash_id": ids["fondo"],
        "posting_date": FECHA.isoformat(),
        "delivered_to": "Ana Cajera",
        "concept": "Compra de insumos de limpieza",
        "amount": "50.00",
        "cost_center_code": ids["centro"],
    }
    datos.update(reemplazos)
    return client.post("/cash_management/petty-cash-voucher/new", data=datos)


def test_post_invalido_rehidrata_compania_fondo_moneda_y_dimension(caja_vale_estado):
    """Un importe en cero re-renderiza el formulario con los valores enviados."""
    application, ids = caja_vale_estado
    client = application.test_client()
    _iniciar(client)

    response = _postear_vale(client, ids, amount="0.00")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "El importe del vale debe ser mayor a cero." in cuerpo
    assert re.search(r'initialValue:\s*"cacao"', cuerpo)
    assert re.search(r'initialLabel:\s*"cacao"', cuerpo)
    assert re.search(rf'initialValue:\s*"{re.escape(ids["fondo"])}"', cuerpo)
    assert re.search(rf'initialLabel:\s*"cacao - {re.escape("Fondo Vales Rehidratados")}"', cuerpo)
    assert re.search(r'id="pc_currency"[^>]*value="NIO"', cuerpo)
    assert re.search(rf'initialValue:\s*"{re.escape(ids["centro"])}"', cuerpo)
    with application.app_context():
        assert database.session.execute(database.select(PettyCashVoucher)).scalars().all() == []


def test_post_sin_concepto_rehidrata_los_selectores_y_no_persiste(caja_vale_estado):
    """Sin concepto, el formulario conserva compañía, fondo y moneda elegidos."""
    application, ids = caja_vale_estado
    client = application.test_client()
    _iniciar(client)

    response = _postear_vale(client, ids, concept="   ")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "El concepto del vale es obligatorio." in cuerpo
    assert re.search(r'initialValue:\s*"cacao"', cuerpo)
    assert re.search(rf'initialValue:\s*"{re.escape(ids["fondo"])}"', cuerpo)
    assert re.search(r'id="pc_currency"[^>]*value="NIO"', cuerpo)
    with application.app_context():
        assert database.session.execute(database.select(PettyCashVoucher)).scalars().all() == []


def test_post_valido_persiste_el_vale(caja_vale_estado):
    """Control positivo: el mismo formulario persiste el vale cuando el POST es válido."""
    application, ids = caja_vale_estado
    client = application.test_client()
    _iniciar(client)

    response = _postear_vale(client, ids)

    assert response.status_code == 302
    with application.app_context():
        vale = database.session.execute(database.select(PettyCashVoucher)).scalar_one()
        assert vale.company == "cacao"
        assert vale.petty_cash_id == ids["fondo"]
        assert vale.concept == "Compra de insumos de limpieza"


def test_lista_de_vales_borrador_no_enlaza_edicion_inexistente(caja_vale_estado):
    """La lista presenta acciones de estado disponibles para un borrador."""
    application, ids = caja_vale_estado
    client = application.test_client()
    _iniciar(client)
    _postear_vale(client, ids)

    response = client.get("/cash_management/petty-cash-voucher/list")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Compra de insumos de limpieza" in cuerpo
    assert "Entregar" in cuerpo
    assert "Cancelar" in cuerpo
    assert "Editar" not in cuerpo
    assert "caja_chica_vale_editar" not in cuerpo


def test_formulario_limpia_la_moneda_al_cambiar_compania(caja_vale_estado):
    """El formulario conecta company-selected con la limpieza de la moneda del fondo."""
    application, _ids = caja_vale_estado
    client = application.test_client()
    _iniciar(client)

    response = client.get("/cash_management/petty-cash-voucher/new")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "company-selected" in cuerpo
    assert "getElementById('pc_currency')" in cuerpo
