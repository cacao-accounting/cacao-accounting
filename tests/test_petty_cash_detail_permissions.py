# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Permisos efectivos en el detalle de caja chica (#2089).

Escenario de negocio: una cajera con permiso de ``cash.consultar`` consulta el
detalle de un fondo para revisar saldos, pero la interfaz no debe ofrecerle
acciones de escritura (alternar estado, marcar predeterminada, editar). Los
enlaces solo se renderizan cuando el permiso efectivo ``can_edit_cash`` es
verdadero; el guard del servidor sigue rechazando el POST directo con 403.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Book,
    Currency,
    Entity,
    Modules,
    PettyCashAccount,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "caja-detalle-permisos-2026"


@pytest.fixture
def caja_detalle():
    """Fondo de caja chica con un usuario solo-consulta y un administrador."""
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
                    id="consulta-detalle",
                    user="consulta-detalle",
                    name="Cajera Consulta",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="administrador-caja",
                    user="administrador-caja",
                    name="Administrador Tesoreria",
                    password=proteger_passwd(CONTRASENA),
                    classification="admin",
                    active=True,
                    company="cacao",
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
        database.session.add_all(
            [
                UserCompanyAccess(user_id="consulta-detalle", company_code="cacao"),
                UserCompanyAccess(user_id="administrador-caja", company_code="cacao"),
            ]
        )
        database.session.flush()
        cuenta = Accounts(
            code="1.01.05.001",
            name="Caja Chica Detalle",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="petty_cash",
        )
        database.session.add(cuenta)
        database.session.flush()
        fondo = PettyCashAccount(
            company="cacao",
            account_id=cuenta.id,
            name="Fondo Detalle Permisos",
            currency="NIO",
            float_amount=Decimal("500"),
            is_default=False,
            is_active=True,
        )
        database.session.add(fondo)
        database.session.flush()
        rol_consulta = Roles(name="cash-solo-consulta", note="Consulta caja chica sin editar")
        database.session.add(rol_consulta)
        database.session.flush()
        modulo_caja = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one()
        database.session.add(
            RolesAccess(
                rol_id=rol_consulta.id,
                module_id=modulo_caja.id,
                access=True,
                view=True,
                edit=False,
                create=False,
            )
        )
        database.session.add(RolesUser(user_id="consulta-detalle", role_id=rol_consulta.id, active=True))
        database.session.commit()
        ids = {"fondo": fondo.id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client, usuario: str) -> None:
    response = client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def _urls_de_accion(fondo_id: str) -> tuple[str, str, str]:
    """URLs de toggle, predeterminada y editar del detalle de caja chica."""
    return (
        f"/cash_management/petty-cash/{fondo_id}/toggle",
        f"/cash_management/petty-cash/{fondo_id}/default",
        f"/cash_management/petty-cash/{fondo_id}/edit",
    )


def test_detalle_sin_permiso_edicion_oculta_acciones(caja_detalle):
    """El usuario solo-consulta ve el detalle pero sin formularios de escritura."""
    application, ids = caja_detalle
    client = application.test_client()
    _iniciar(client, "consulta-detalle")

    response = client.get(f"/cash_management/petty-cash/{ids['fondo']}")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Fondo Detalle Permisos" in cuerpo
    for url in _urls_de_accion(ids["fondo"]):
        assert url not in cuerpo


def test_detalle_para_administrador_muestra_acciones(caja_detalle):
    """Control positivo: el administrador sigue viendo toggle, predeterminada y editar."""
    application, ids = caja_detalle
    client = application.test_client()
    _iniciar(client, "administrador-caja")

    response = client.get(f"/cash_management/petty-cash/{ids['fondo']}")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    for url in _urls_de_accion(ids["fondo"]):
        assert url in cuerpo


def test_toggle_rechaza_usuario_solo_consulta(caja_detalle):
    """El guard del servidor mantiene el 403 aunque la UI oculte el botón."""
    application, ids = caja_detalle
    client = application.test_client()
    _iniciar(client, "consulta-detalle")

    response = client.post(f"/cash_management/petty-cash/{ids['fondo']}/toggle")

    assert response.status_code == 403
    with application.app_context():
        fondo = database.session.get(PettyCashAccount, ids["fondo"])
        assert fondo is not None and fondo.is_active is True


def test_editar_caja_chica_persiste_nombre(caja_detalle):
    """El nombre enviado por el formulario actualiza el mismo fondo."""
    application, ids = caja_detalle
    client = application.test_client()
    _iniciar(client, "administrador-caja")

    response = client.post(
        f"/cash_management/petty-cash/{ids['fondo']}/edit",
        data={"name": "Fondo Operativo Renombrado"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    with application.app_context():
        fondo = database.session.get(PettyCashAccount, ids["fondo"])
        assert fondo is not None and fondo.name == "Fondo Operativo Renombrado"


@pytest.mark.parametrize("new_name", ["", "Fondo Duplicado"])
def test_editar_caja_chica_rechaza_nombre_vacio_o_duplicado(caja_detalle, new_name):
    """La edición conserva nombre válido ante vacío o duplicado en la compañía."""
    application, ids = caja_detalle
    if new_name == "Fondo Duplicado":
        with application.app_context():
            fondo = database.session.get(PettyCashAccount, ids["fondo"])
            assert fondo is not None
            database.session.add(
                PettyCashAccount(
                    company=fondo.company,
                    account_id=fondo.account_id,
                    name=new_name,
                    currency=fondo.currency,
                    float_amount=Decimal("0"),
                    is_default=False,
                    is_active=True,
                )
            )
            database.session.commit()

    client = application.test_client()
    _iniciar(client, "administrador-caja")
    response = client.post(
        f"/cash_management/petty-cash/{ids['fondo']}/edit",
        data={"name": new_name},
        follow_redirects=True,
    )

    assert response.status_code == 200
    with application.app_context():
        fondo = database.session.get(PettyCashAccount, ids["fondo"])
        assert fondo is not None and fondo.name == "Fondo Detalle Permisos"
