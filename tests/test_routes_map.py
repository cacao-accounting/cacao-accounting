"""Smoke test del mapa de rutas usando el url_map real de la aplicación."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask import Flask, url_for

from cacao_accounting import create_app
from cacao_accounting.config import configuracion

ALLOWED_STATUS_CODES = {200, 302, 303, 307, 308, 400, 401, 403, 405}
EXCLUDED_ENDPOINT_PREFIXES = {"static"}
EXCLUDED_RULES = {
    "/exit",
    "/logout",
    "/salir",
}


@pytest.fixture()
def app_ctx() -> Iterator[Flask]:
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test-routes-map-secret",
        }
    )
    with app.app_context():
        from cacao_accounting.database import CacaoConfig, Currency, Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                CacaoConfig(key="SETUP_COMPLETE", value="True"),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
                Modules(module="admin", default=True, enabled=True),
                Modules(module="accounting", default=True, enabled=True),
                Modules(module="cash", default=True, enabled=True),
                Modules(module="purchases", default=True, enabled=True),
                Modules(module="inventory", default=True, enabled=True),
                Modules(module="sales", default=True, enabled=True),
            ]
        )
        database.session.commit()
        yield app


@pytest.fixture()
def client(app_ctx: Flask):
    return app_ctx.test_client()


def _login_admin(client) -> None:
    from cacao_accounting.database import User

    admin = User.query.filter_by(user="admin").first()
    assert admin is not None
    with client.session_transaction() as session:
        session["_user_id"] = admin.id
        session["_fresh"] = True


def _iter_get_routes(app: Flask) -> list[str]:
    routes: list[str] = []
    with app.test_request_context():
        for rule in app.url_map.iter_rules():
            if "GET" not in rule.methods:
                continue
            if any(rule.endpoint.startswith(prefix) for prefix in EXCLUDED_ENDPOINT_PREFIXES):
                continue
            if rule.rule in EXCLUDED_RULES:
                continue
            if rule.arguments.difference((rule.defaults or {}).keys()):
                continue
            routes.append(url_for(rule.endpoint, **(rule.defaults or {})))
    return sorted(set(routes))


def test_all_static_get_routes_render_without_server_errors(app_ctx: Flask, client) -> None:
    _login_admin(client)

    for route in _iter_get_routes(app_ctx):
        response = client.get(route, follow_redirects=False)
        if route.startswith("/api/") and response.status_code == 404:
            continue
        assert response.status_code in ALLOWED_STATUS_CODES, f"Ruta {route} devolvió estado inesperado {response.status_code}"
        assert response.status_code != 404, f"Ruta {route} devolvió 404"
        assert response.status_code < 500, f"Ruta {route} devolvió error de servidor {response.status_code}"


def test_accounting_module_home_renders_successfully(client) -> None:
    _login_admin(client)

    response = client.get("/accounting/", follow_redirects=False)

    assert response.status_code == 200
    assert b"M\xc3\xb3dulo de Contabilidad" in response.data
