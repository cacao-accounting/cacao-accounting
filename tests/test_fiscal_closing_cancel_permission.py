# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1786: solo el administrador anula un cierre fiscal por la ruta genérica."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from babel.support import Translations
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Book,
    ComprobanteContable,
    Currency,
    Entity,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture
def cierre_fiscal_escenario():
    """Cierre fiscal posteado con un usuario contable que no es administrador."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "SECRET_KEY": "fiscal-cancel-secret",
        }
    )
    sufijo = uuid4().hex[:6]
    contador_id = f"contador-{sufijo}"
    admin_id = f"admin-{sufijo}"
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id=f"TAX-{sufijo}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.commit()
        database.session.add_all(
            [
                Book(
                    entity="cacao",
                    code=f"BOOK-{sufijo}",
                    name="Libro",
                    status="activo",
                    is_primary=True,
                    currency="NIO",
                ),
                User(id=contador_id, user=contador_id, name="Contador", password=b"x", active=True, company="cacao"),
                User(
                    id=admin_id,
                    user=admin_id,
                    name="Admin",
                    password=b"x",
                    active=True,
                    company="cacao",
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="accounting")).scalar_one()
        rol = Roles(name=f"contable-{sufijo}", note="Anulación contable")
        database.session.add(rol)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=rol.id, module_id=module_id, access=True, view=True, edit=True, set_null=True),
                RolesUser(user_id=contador_id, role_id=rol.id, active=True),
                UserCompanyAccess(user_id=contador_id, company_code="cacao"),
                UserCompanyAccess(user_id=admin_id, company_code="cacao"),
            ]
        )
        cierre = ComprobanteContable(
            entity="cacao",
            date=date(2026, 12, 31),
            status="submitted",
            user_id=admin_id,
            voucher_type="journal_entry",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            is_closing=True,
            is_fiscal_year_closing=True,
        )
        database.session.add(cierre)
        database.session.commit()
        ids = {"cierre": cierre.id, "contador": contador_id, "admin": admin_id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _cliente(app, user_id: str):
    """Autentica un cliente de prueba como el usuario indicado."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_contador_no_puede_anular_cierre_fiscal_por_ruta_generica(cierre_fiscal_escenario):
    """La ruta genérica rechaza el cierre fiscal para actores no administradores."""
    app, ids = cierre_fiscal_escenario
    client = _cliente(app, ids["contador"])

    response = client.post(
        f"/accounting/journal/{ids['cierre']}/cancel",
        data={"reason": "Anulación indebida", "cancellation_date": "2026-12-31"},
    )

    assert response.status_code == 403
    with app.app_context():
        journal = database.session.get(ComprobanteContable, ids["cierre"])
        assert journal.status == "submitted"


def test_contador_no_ve_el_boton_de_anulacion_del_cierre(cierre_fiscal_escenario):
    """La interfaz no ofrece la anulación genérica de un cierre fiscal."""
    app, ids = cierre_fiscal_escenario
    client = _cliente(app, ids["contador"])

    response = client.get(f"/accounting/journal/{ids['cierre']}")

    assert response.status_code == 200
    assert "Anular comprobante" not in response.get_data(as_text=True)


def test_administrador_conserva_la_accion_de_anulacion(cierre_fiscal_escenario):
    """El administrador del sistema sigue viendo la acción genérica."""
    app, ids = cierre_fiscal_escenario
    client = _cliente(app, ids["admin"])

    response = client.get(f"/accounting/journal/{ids['cierre']}")

    assert response.status_code == 200
    assert "Anular comprobante" in response.get_data(as_text=True)


def test_guard_de_anulacion_del_cierre_tiene_traduccion_inglesa():
    """El mensaje del guard está en el catálogo compilado que usa el entorno inglés."""
    catalogo = Translations.load(
        str(Path(__file__).resolve().parents[1] / "cacao_accounting" / "translations"),
        locales=["en"],
        domain="messages",
    )

    assert (
        catalogo.gettext("Solo el administrador del sistema puede anular un cierre fiscal.")
        == "Only the system administrator can cancel a fiscal year close."
    )
