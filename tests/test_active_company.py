# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de la compania activa de la interfaz (cloud only)."""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    Entity,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

MODULES = ("accounting", "cash", "purchases", "inventory", "sales")


@pytest.fixture()
def app():
    """Crea una aplicacion aislada con dos companias autorizadas."""
    flask_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "active-company-tests",
        }
    )
    with flask_app.app_context():
        database.create_all()
        _seed()
        yield flask_app


def _login(client, user_id: str) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def _seed() -> None:
    database.session.add_all([Modules(id=f"MOD-{name.upper()}", module=name, default=True, enabled=True) for name in MODULES])
    database.session.add_all(
        [
            Roles(id="ROLE-USER", name="accounting_user", note="Accounting user"),
            User(id="USER-CACAO", user="user_cacao", password=b"x", active=True),
            User(id="USER-BOTH", user="user_both", password=b"x", active=True),
            Entity(
                id="ID-CACAO", code="CACAO", name="Cacao", company_name="Cacao SA", tax_id="J1", currency="NIO", enabled=True
            ),
            Entity(id="ID-CAFE", code="CAFE", name="Cafe", company_name="Cafe SA", tax_id="J2", currency="NIO", enabled=True),
            Entity(
                id="ID-OFF",
                code="OFF",
                name="Off",
                company_name="Off SA",
                tax_id="J3",
                currency="NIO",
                enabled=False,
            ),
        ]
    )
    database.session.flush()
    database.session.add_all(
        [
            RolesUser(user_id="USER-CACAO", role_id="ROLE-USER", active=True),
            RolesUser(user_id="USER-BOTH", role_id="ROLE-USER", active=True),
        ]
    )
    database.session.add_all(
        [RolesAccess(rol_id="ROLE-USER", module_id=f"MOD-{name.upper()}", access=True, view=True) for name in MODULES]
    )
    database.session.add_all(
        [
            UserCompanyAccess(user_id="USER-CACAO", company_code="CACAO"),
            UserCompanyAccess(user_id="USER-BOTH", company_code="CACAO"),
            UserCompanyAccess(user_id="USER-BOTH", company_code="CAFE"),
        ]
    )
    database.session.commit()


def test_authorized_company_codes_only_returns_assigned(app):
    """Los codigos autorizados se limitan a las companias asignadas."""
    from flask_login import login_user

    from cacao_accounting.company_context import authorized_company_codes

    with app.test_request_context():
        login_user(database.session.get(User, "USER-CACAO"))
        assert authorized_company_codes() == ["CACAO"]

    with app.test_request_context():
        login_user(database.session.get(User, "USER-BOTH"))
        assert authorized_company_codes() == ["CACAO", "CAFE"]
        assert "OFF" not in authorized_company_codes()


def test_get_active_company_defaults_to_first_authorized(app):
    """Sin cookie ni parametro se usa la primera compania autorizada."""
    from cacao_accounting.company_context import get_active_company

    with app.test_request_context():
        from flask_login import login_user

        login_user(database.session.get(User, "USER-CACAO"))
        assert get_active_company() == "CACAO"


def test_get_active_company_prefers_requested_then_cookie(app):
    """La compania solicitada y la cookie tienen prioridad sobre la primera."""
    from cacao_accounting.company_context import get_active_company

    with app.test_request_context(headers={"Cookie": "cacao_active_company=CAFE"}):
        from flask_login import login_user

        login_user(database.session.get(User, "USER-BOTH"))
        assert get_active_company() == "CAFE"
        assert get_active_company("CAFE") == "CAFE"
        assert get_active_company("OFF") == "CAFE"


def test_set_active_company_writes_cookie_only_when_authorized(app):
    """La cookie solo se escribe para una compania autorizada."""
    from flask import make_response

    from cacao_accounting.company_context import ACTIVE_COMPANY_COOKIE, set_active_company

    with app.test_request_context():
        from flask_login import login_user

        login_user(database.session.get(User, "USER-CACAO"))
        response = make_response("ok")
        assert set_active_company(response, "CAFE") is False
        assert ACTIVE_COMPANY_COOKIE not in response.headers.get("Set-Cookie", "")

    with app.test_request_context():
        from flask_login import login_user

        login_user(database.session.get(User, "USER-BOTH"))
        response = make_response("ok")
        assert set_active_company(response, "CAFE") is True
        assert f"{ACTIVE_COMPANY_COOKIE}=CAFE" in response.headers.get("Set-Cookie", "")


def test_change_company_route_sets_cookie_and_blocks_open_redirect(app):
    """La ruta de cambio persiste la compania y evita redirecciones externas."""
    client = app.test_client()
    _login(client, "USER-BOTH")

    response = client.get("/auth/company?company=CAFE&next=/accounting/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/accounting/"
    assert "cacao_active_company=CAFE" in response.headers.get("Set-Cookie", "")

    response = client.get("/auth/company?company=CAFE&next=//evil.example.com")
    assert response.status_code == 302
    from flask import url_for

    with app.test_request_context():
        expected = url_for("cacao_app.pagina_inicio")
    assert response.headers["Location"] == expected


def test_change_company_route_rejects_unauthorized(app):
    """Un usuario no puede fijar una compania sin acceso."""
    client = app.test_client()
    _login(client, "USER-CACAO")

    response = client.get("/auth/company?company=CAFE&next=/app")
    assert response.status_code == 302
    assert "cacao_active_company=CAFE" not in response.headers.get("Set-Cookie", "")


def test_selector_is_available_only_in_cloud_with_multiple_companies(app):
    """El selector se muestra solo en cloud y con mas de una compania."""
    from cacao_accounting.company_context import active_company_is_selectable

    with app.test_request_context():
        from flask_login import login_user

        login_user(database.session.get(User, "USER-CACAO"))
        assert active_company_is_selectable() is False

    with app.test_request_context():
        from flask_login import login_user

        login_user(database.session.get(User, "USER-BOTH"))
        assert active_company_is_selectable() is True

        app.config["MODO_ESCRITORIO"] = True
        try:
            assert active_company_is_selectable() is False
        finally:
            app.config.pop("MODO_ESCRITORIO", None)


@pytest.mark.parametrize(
    "endpoint",
    ["/accounting/", "/sales/", "/buying/", "/inventory/", "/cash_management/"],
)
def test_module_dashboard_report_links_carry_active_company(app, endpoint):
    """Los dashboards enlazan a reportes con la compania activa."""
    client = app.test_client()
    _login(client, "USER-BOTH")
    client.set_cookie("cacao_active_company", "CAFE")

    response = client.get(endpoint)
    assert response.status_code == 200
    assert b"company=CAFE" in response.data


def test_resolve_company_no_longer_falls_back_to_default(app):
    """Una compania inexistente falla en lugar de caer a la predeterminada."""
    from werkzeug.exceptions import BadRequest

    from cacao_accounting.reportes.helpers import _resolve_company

    with app.test_request_context():
        from flask_login import login_user

        login_user(database.session.get(User, "USER-BOTH"))
        assert _resolve_company("CAFE") == "CAFE"
        with pytest.raises(BadRequest):
            _resolve_company("NOPE")


def test_financial_report_filters_reject_company_without_access(app):
    """Un usuario no puede consultar reportes financieros de una compania ajena."""
    from werkzeug.exceptions import Forbidden

    from cacao_accounting.reportes.helpers import _financial_filters

    with app.test_request_context("/reports/balance-sheet?company=CAFE"):
        from flask_login import login_user

        login_user(database.session.get(User, "USER-CACAO"))
        with pytest.raises(Forbidden):
            _financial_filters()

    with app.test_request_context("/reports/balance-sheet?company=CACAO"):
        from flask_login import login_user

        login_user(database.session.get(User, "USER-CACAO"))
        assert _financial_filters().company == "CACAO"
