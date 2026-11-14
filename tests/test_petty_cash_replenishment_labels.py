# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Etiquetas legibles de fondos en la lista de reposiciones (#2036).

Escenario de negocio: la tesorera revisa las solicitudes de reposición y debe
leer el nombre del fondo de caja chica y su compañía, no un identificador
técnico generado por la base de datos. La lista resuelve ``fondos.get(...)`` y
solo usa el id crudo como último recurso cuando el fondo no existe.
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
    Book,
    Currency,
    Entity,
    Modules,
    PettyCashAccount,
    PettyCashReplenishment,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "caja-reposicion-lista-2026"
FECHA = date(2026, 11, 10)


def _crear_cuenta(db, codigo: str, nombre: str) -> str:
    """Crea una cuenta contable de tipo caja chica y devuelve su id."""
    cuenta = Accounts(
        code=codigo,
        name=nombre,
        entity="cacao",
        group=False,
        active=True,
        enabled=True,
        account_type="petty_cash",
    )
    db.session.add(cuenta)
    db.session.flush()
    return cuenta.id


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "supervisor-caja", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


@pytest.fixture
def caja_reposicion_lista():
    """Dos fondos de caja chica con una reposición cada uno en cacao."""
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
                    id="supervisor-caja",
                    user="supervisor-caja",
                    name="Supervisor de Caja",
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
        database.session.add(UserCompanyAccess(user_id="supervisor-caja", company_code="cacao"))
        database.session.flush()
        rol_lectura = Roles(name="cash-lista-reposiciones", note="Lee reposiciones de caja chica")
        database.session.add(rol_lectura)
        database.session.flush()
        modulo_caja = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one()
        database.session.add(RolesAccess(rol_id=rol_lectura.id, module_id=modulo_caja.id, access=True, view=True))
        database.session.add(RolesUser(user_id="supervisor-caja", role_id=rol_lectura.id, active=True))
        database.session.flush()
        fondo_norte = PettyCashAccount(
            company="cacao",
            account_id=_crear_cuenta(database, "1.01.05.001", "Caja Chica Norte"),
            name="Fondo Caja Chica Norte",
            currency="NIO",
            float_amount=Decimal("800"),
            is_default=True,
            is_active=True,
        )
        fondo_puerto = PettyCashAccount(
            company="cacao",
            account_id=_crear_cuenta(database, "1.01.05.002", "Caja Chica Puerto"),
            name="Fondo Caja Chica Puerto",
            currency="NIO",
            float_amount=Decimal("300"),
            is_default=False,
            is_active=True,
        )
        database.session.add_all([fondo_norte, fondo_puerto])
        database.session.flush()
        reposiciones = [
            PettyCashReplenishment(
                company="cacao",
                petty_cash_id=fondo_norte.id,
                request_date=FECHA,
                amount=Decimal("120"),
                status="solicitado",
                docstatus=1,
                transaction_currency="NIO",
            ),
            PettyCashReplenishment(
                company="cacao",
                petty_cash_id=fondo_puerto.id,
                request_date=FECHA,
                amount=Decimal("45"),
                status="borrador",
                docstatus=0,
                transaction_currency="NIO",
            ),
        ]
        database.session.add_all(reposiciones)
        database.session.commit()
        ids = {
            "fondo_norte": fondo_norte.id,
            "fondo_puerto": fondo_puerto.id,
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_reposicion_lista_muestra_nombre_y_compania_del_fondo(caja_reposicion_lista):
    """La fila de reposición identifica el fondo por nombre y compañía."""
    application, ids = caja_reposicion_lista
    client = application.test_client()
    _iniciar(client)

    response = client.get("/cash_management/petty-cash-replenishment/list")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Fondo Caja Chica Norte" in cuerpo
    assert "(cacao)" in cuerpo
    assert ids["fondo_norte"] not in cuerpo


def test_reposicion_lista_resuelve_cada_fondo_con_su_propia_etiqueta(caja_reposicion_lista):
    """Dos fondos distintos se mapean por id sin filtrar ids crudos."""
    application, ids = caja_reposicion_lista
    client = application.test_client()
    _iniciar(client)

    response = client.get("/cash_management/petty-cash-replenishment/list")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Fondo Caja Chica Norte" in cuerpo
    assert "Fondo Caja Chica Puerto" in cuerpo
    assert ids["fondo_norte"] not in cuerpo
    assert ids["fondo_puerto"] not in cuerpo
