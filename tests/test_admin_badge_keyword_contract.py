# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1912: el badge de permisos usa el keyword real de module_badge.

El contrato estático se conserva como segunda barrera; la regresión principal
renderiza el índice de Configuración en Cloud y Desktop y exige el badge real,
de modo que un keyword incompatible vuelva a producir un 500.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, database

RAIZ = Path(__file__).resolve().parents[1] / "cacao_accounting"


def test_plantilla_admin_usa_required():
    """admin.html no puede llamar module_badge con required_permission."""
    plantilla = (RAIZ / "admin" / "templates" / "admin.html").read_text(encoding="utf-8")

    assert "module_badge(" in plantilla
    assert "required_permission=" not in plantilla


@pytest.fixture
def admin_module_activo(app):
    """Habilita el módulo administrativo durante la prueba Cloud."""
    with app.app_context():
        module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if module is None:
            module = Modules(module="admin", default=False, enabled=True)
            database.session.add(module)
            creado = True
        else:
            creado = False
            anterior = module.enabled
            module.enabled = True
        database.session.commit()
    yield
    with app.app_context():
        module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if module is not None:
            if creado:
                database.session.delete(module)
            else:
                module.enabled = anterior
            database.session.commit()


def test_el_indice_de_configuracion_renderiza_el_badge_en_cloud(app, authenticated_client, admin_module_activo):
    """Cloud renderiza los badges del menú de Configuración."""
    response = authenticated_client("admin").get("/settings")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "ca-module-state" in cuerpo
    assert 'data-status="ok"' in cuerpo


@pytest.fixture
def desktop_badge_app():
    """App Desktop con administrador y módulos administrativos activos."""
    sufijo = uuid4().hex[:6]
    company = f"d{sufijo}"
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
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="admin", default=True, enabled=True),
                Modules(module="accounting", default=True, enabled=True),
                Entity(
                    code=company,
                    name="Escritorio",
                    company_name=f"Compañía Escritorio {sufijo}",
                    tax_id=f"TAX-D-{sufijo}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id=f"desktop-badge-{sufijo}",
                    user=f"desktop-badge-{sufijo}",
                    name="Administrador Escritorio",
                    password=b"unused",
                    active=True,
                    company=company,
                    classification="admin",
                ),
            ]
        )
        database.session.commit()
        user_id = f"desktop-badge-{sufijo}"
    yield application, user_id
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_el_indice_de_configuracion_renderiza_el_badge_en_desktop(desktop_badge_app):
    """Desktop conserva el mismo render de badges que Cloud."""
    application, user_id = desktop_badge_app
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True

    response = client.get("/settings")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "ca-module-state" in cuerpo
    assert 'data-status="ok"' in cuerpo
