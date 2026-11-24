# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1885: las listas de caja chica muestran estados traducibles.

Los códigos persistidos (``borrador``, ``solicitado``, ``reembolsado``, etc.)
gobiernan las transiciones del servicio y no deben cambiar; la presentación sí
debe usar gettext. La regresión renderiza ambas listas con todos los estados y
verifica que la etiqueta legible reemplace al código, además de comprobar el
catálogo inglés para cada una.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from flask_babel import force_locale, gettext

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
    PettyCashReconciliation,
    PettyCashReplenishment,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "caja-estados-2026"
ETIQUETAS = {
    "borrador": "Borrador",
    "conciliado": "Conciliado",
    "solicitado": "Solicitado",
    "aprobado": "Aprobado",
    "reembolsado": "Reembolsado",
    "cancelado": "Cancelado",
}
TRADUCCIONES_INGLES = {
    "Borrador": "Draft",
    "Conciliado": "Reconciled",
    "Solicitado": "Requested",
    "Aprobado": "Approved",
    "Reembolsado": "Reimbursed",
    "Cancelado": "Cancelled",
}


def _crear_cuenta() -> str:
    """Crea la cuenta contable del fondo de caja chica."""
    cuenta = Accounts(
        code="1.01.05.1885",
        name="Caja Chica Estados",
        entity="cacao",
        group=False,
        active=True,
        enabled=True,
        account_type="petty_cash",
    )
    database.session.add(cuenta)
    database.session.flush()
    return cuenta.id


def _iniciar(client) -> None:
    """Autentica al supervisor de caja chica."""
    response = client.post("/login", data={"usuario": "supervisor-caja", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


@pytest.fixture
def caja_chica_estados():
    """Fondo con conciliaciones y reposiciones en todos los estados renderizados."""
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
        rol = Roles(name="cash-estados", note="Lee estados de caja chica")
        database.session.add(rol)
        database.session.flush()
        modulo_caja = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one()
        database.session.add_all(
            [
                RolesAccess(rol_id=rol.id, module_id=modulo_caja.id, access=True, view=True),
                RolesUser(user_id="supervisor-caja", role_id=rol.id, active=True),
            ]
        )
        database.session.flush()
        fondo = PettyCashAccount(
            company="cacao",
            account_id=_crear_cuenta(),
            name="Fondo de Prueba",
            currency="NIO",
            float_amount=Decimal("500"),
            is_default=True,
            is_active=True,
        )
        database.session.add(fondo)
        database.session.flush()
        database.session.add_all(
            [
                PettyCashReconciliation(
                    company="cacao",
                    petty_cash_id=fondo.id,
                    reconciliation_date=date(2026, 11, indice),
                    expected_cash=Decimal("100"),
                    counted_cash=Decimal("100"),
                    status=status,
                    docstatus=1 if status != "borrador" else 0,
                )
                for indice, status in enumerate(("borrador", "conciliado", "cancelado"), start=1)
            ]
        )
        database.session.add_all(
            [
                PettyCashReplenishment(
                    company="cacao",
                    petty_cash_id=fondo.id,
                    request_date=date(2026, 11, 2),
                    amount=Decimal("10"),
                    status=status,
                    docstatus=0 if status == "borrador" else 1,
                    transaction_currency="NIO",
                    document_no=f"REP-1885-{status}",
                )
                for status in ("borrador", "solicitado", "aprobado", "reembolsado", "cancelado")
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_conciliaciones_muestran_estados_traducidos(caja_chica_estados):
    """La lista no imprime los códigos internos de conciliación."""
    client = caja_chica_estados.test_client()
    _iniciar(client)

    response = client.get("/cash_management/petty-cash-reconciliation/list")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    for codigo in ("borrador", "conciliado", "cancelado"):
        assert f">{codigo}<" not in cuerpo
        assert f">{ETIQUETAS[codigo]}<" in cuerpo


def test_reposiciones_muestran_estados_traducidos(caja_chica_estados):
    """La lista no imprime los códigos internos de reposición."""
    client = caja_chica_estados.test_client()
    _iniciar(client)

    response = client.get("/cash_management/petty-cash-replenishment/list")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    for codigo in ("borrador", "solicitado", "aprobado", "reembolsado", "cancelado"):
        assert f">{codigo}<" not in cuerpo
        assert f">{ETIQUETAS[codigo]}<" in cuerpo


def test_el_catalogo_ingles_traduce_los_estados_de_caja_chica(app):
    """Cada etiqueta visible tiene traducción inglesa en el catálogo."""
    with app.app_context(), force_locale("en"):
        for etiqueta, ingles in TRADUCCIONES_INGLES.items():
            assert gettext(etiqueta) == ingles
