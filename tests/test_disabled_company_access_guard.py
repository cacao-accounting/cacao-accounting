"""Desktop administrators must not access disabled companies (#1338)."""

from __future__ import annotations

import pytest
from flask_login import login_user
from werkzeug.exceptions import Forbidden

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, database
from cacao_accounting.decorators import exige_acceso_compania


@pytest.fixture
def desktop_admin_app():
    """Build a desktop database with one enabled and one disabled company."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "MODO_ESCRITORIO": True,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.add(Modules(module="cash", default=True, enabled=True))
        database.session.add(
            User(
                id="desktop-admin", user="desktop-admin", name="Admin", password=b"unused", active=True, classification="admin"
            )
        )
        database.session.add_all(
            [
                Entity(code="ACTIVE", name="Active", company_name="Active", tax_id="T-ACTIVE", currency="NIO", enabled=True),
                Entity(
                    code="DISABLED",
                    name="Disabled",
                    company_name="Disabled",
                    tax_id="T-DISABLED",
                    currency="NIO",
                    enabled=False,
                ),
            ]
        )
        database.session.commit()
    yield app
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authorize_company(app, company: str) -> None:
    """Run the production company guard as the desktop administrator."""
    from cacao_accounting.database import User

    with app.test_request_context("/"):
        user = database.session.get(User, "desktop-admin")
        login_user(user)
        exige_acceso_compania("cash", company, "consultar")


def test_desktop_admin_can_access_enabled_company(desktop_admin_app):
    """Desktop's single-company admin bypass still works for enabled entities."""
    _authorize_company(desktop_admin_app, "ACTIVE")


def test_desktop_admin_cannot_access_disabled_company(desktop_admin_app):
    """An inactive entity fails the company guard even for a desktop admin."""
    with pytest.raises(Forbidden):
        _authorize_company(desktop_admin_app, "DISABLED")
