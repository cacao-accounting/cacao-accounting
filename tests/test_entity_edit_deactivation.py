"""#1771/#2231: no permite desactivar la única entidad en modo Desktop."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, database


@pytest.fixture
def desktop_entity_app(tmp_path):
    suffix = uuid4().hex[:8]
    password = "AdminPass!123"
    original_tax_id = f"J-{suffix}"
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'entity-desktop.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
            "SECRET_KEY": "desktop-entity-test",
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.add(Modules(module="accounting", default=True, enabled=True))
        database.session.add(
            User(
                id=f"admin-{suffix}",
                user=f"admin-{suffix}",
                name="Admin",
                password=proteger_passwd(password),
                active=True,
                classification="admin",
            )
        )
        database.session.add(
            Entity(
                code="C001",
                company_name="Compañía Única",
                name="Única",
                tax_id=original_tax_id,
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.commit()

    yield app, f"admin-{suffix}", password, original_tax_id

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_edit_route_rejects_disabling_only_entity_in_desktop(desktop_entity_app):
    app, username, password, original_tax_id = desktop_entity_app
    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"usuario": username, "acceso": password},
            follow_redirects=True,
        )
        assert login.status_code == 200

        response = client.post(
            "/accounting/entity/edit/C001",
            data={
                "id_fiscal": "J-EDIT",
                "nombre_comercial": "Única",
                "razon_social": "Compañía Única",
                "correo_electronico": "",
                "telefono1": "",
                "telefono2": "",
                "fax": "",
                "web": "",
                # "habilitado" ausente: simula desmarcar la única entidad en Desktop
            },
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert "/accounting/entity/C001" in (response.headers.get("Location") or "")

    with app.app_context():
        entity = database.session.execute(database.select(Entity).filter_by(code="C001")).scalar_one()
        assert entity.enabled is True
        assert entity.tax_id == original_tax_id
