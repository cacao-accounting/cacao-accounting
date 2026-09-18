# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes
"""Security tests for user-scoped Redis cache entries and company invalidation."""

from __future__ import annotations

from os import environ
from typing import Any
from unittest.mock import patch

import pytest
from flask_login import login_user
from sqlalchemy import delete

from cacao_accounting import create_app
from cacao_accounting.cache import invalidate_cache
from cacao_accounting.config import TESTING_MODE, configuracion
from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
from cacao_accounting.database import (
    Entity,
    CompanyParty,
    Modules,
    Party,
    User,
    UserCompanyAccess,
    database,
)


class MemoryCache:
    """Small deterministic cache double for cache behavior tests."""

    def __init__(self) -> None:
        """Create an empty fake cache."""
        self.data: dict[str, Any] = {}
        self.set_calls = 0
        self.fail_get = False
        self.fail_set = False

    def get(self, key: str) -> Any:
        """Return a fake cached value or simulate an unavailable backend."""
        if self.fail_get:
            raise OSError("Redis unavailable")
        return self.data.get(key)

    def set(self, key: str, value: Any, timeout: int = 0) -> bool:
        """Store a value or simulate an unavailable backend."""
        if self.fail_set:
            raise OSError("Redis unavailable")
        self.set_calls += 1
        self.data[key] = value
        return True


@pytest.fixture
def app():
    """Create an isolated application and minimal RBAC/company data."""
    database_url = environ.get("DATABASE_URL", "sqlite:///:memory:")
    redis_url = environ.get("CACHE_REDIS_URL") or "redis://localhost:6379/2"
    settings = {
        **configuracion,
        "TESTING": True,
        "SECRET_KEY": "cache-isolation-tests",
        "WTF_CSRF_ENABLED": False,
        "MODO_ESCRITORIO": False,
        "SQLALCHEMY_DATABASE_URI": database_url,
        "CACHE_REDIS_URL": redis_url,
        "CACHE_TYPE": "RedisCache" if redis_url else "SimpleCache",
    }
    application = create_app(settings)
    with application.app_context():
        database.create_all()
        company_a = Entity(
            code="COMP-A",
            company_name="Company Alpha Legal",
            name="Company Alpha",
            tax_id="TAX-COMP-A",
            enabled=True,
        )
        company_b = Entity(
            code="COMP-B",
            company_name="Company Beta Legal",
            name="Company Beta",
            tax_id="TAX-COMP-B",
            enabled=True,
        )
        user_a = User(user="cache-user-a", name="User A", password=b"x", active=True)
        user_b = User(user="cache-user-b", name="User B", password=b"x", active=True)
        admin = User(user="cache-admin", name="Cache Admin", password=b"x", classification="admin", active=True)
        database.session.add_all(
            [company_a, company_b, user_a, user_b, admin, Modules(module="accounting", default=True, enabled=True)]
        )
        database.session.flush()
        database.session.add_all(
            [
                UserCompanyAccess(user_id=user_a.id, company_code=company_a.code),
                UserCompanyAccess(user_id=user_b.id, company_code=company_b.code),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.execute(delete(UserCompanyAccess))
        database.session.execute(delete(User).where(User.user.in_(["cache-user-a", "cache-user-b", "cache-admin"])))
        database.session.execute(delete(Entity).where(Entity.code.in_(["COMP-A", "COMP-B"])))
        database.session.execute(delete(Modules).where(Modules.module == "accounting"))
        database.session.commit()
        database.session.remove()
        database.engine.dispose()


@pytest.fixture
def memory_cache(monkeypatch: pytest.MonkeyPatch) -> MemoryCache:
    """Use a controllable backend while keeping the production cache path."""
    import cacao_accounting.cache as cache_module

    backend = MemoryCache()
    monkeypatch.setattr(cache_module, "cache", backend)
    monkeypatch.setattr(cache_module, "_has_caching", True)
    return backend


def _choices_as(app, username: str) -> list[tuple[str, str]]:
    """Call the company choices helper as one authenticated user."""
    with app.test_request_context("/"):
        user = database.session.execute(database.select(User).filter_by(user=username)).scalar_one()
        login_user(user)
        return obtener_lista_entidades_por_id_razonsocial()


def test_company_choices_are_isolated_between_users(app, memory_cache):
    """A cache warmed by one user cannot disclose its companies to another."""
    choices_a = _choices_as(app, "cache-user-a")
    choices_b = _choices_as(app, "cache-user-b")
    choices_a_again = _choices_as(app, "cache-user-a")

    assert choices_a == [("", ""), ("COMP-A", "Company Alpha")]
    assert choices_b == [("", ""), ("COMP-B", "Company Beta")]
    assert choices_a_again == choices_a
    assert memory_cache.set_calls == 2


def test_smart_select_master_data_is_isolated_between_users(app, memory_cache, monkeypatch):
    """The search endpoint caches only the RBAC-approved result for its user."""
    import sys

    api_module = sys.modules["cacao_accounting.api"]

    with app.app_context():
        database.session.add_all(
            [
                Party(id="CACHE-PARTY-A", code="PARTY-A", name="Party Alpha", is_customer=True, is_active=True),
                Party(id="CACHE-PARTY-B", code="PARTY-B", name="Party Beta", is_customer=True, is_active=True),
                CompanyParty(company="COMP-A", party_id="CACHE-PARTY-A", is_active=True),
                CompanyParty(company="COMP-B", party_id="CACHE-PARTY-B", is_active=True),
            ]
        )
        database.session.commit()

    monkeypatch.setattr(
        api_module,
        "user_can_access_company",
        lambda user, company: (user.user, company.code) in {("cache-user-a", "COMP-A"), ("cache-user-b", "COMP-B")},
    )
    client = app.test_client()

    for username, expected in (("cache-user-a", "CACHE-PARTY-A"), ("cache-user-b", "CACHE-PARTY-B")):
        with app.app_context():
            user_id = database.session.execute(database.select(User.id).filter_by(user=username)).scalar_one()
        with client.session_transaction() as session:
            session["_user_id"] = user_id
            session["_fresh"] = True
        response = client.get("/api/search-select?doctype=customer&q=Party")
        assert response.status_code == 200
        assert [row["id"] for row in response.get_json()["results"]] == [expected]

    with app.app_context():
        user_id = database.session.execute(database.select(User.id).filter_by(user="cache-user-a")).scalar_one()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    assert client.get("/api/search-select?doctype=customer&q=Party").status_code == 200
    assert memory_cache.set_calls == 2


def test_company_scope_is_rechecked_after_access_changes(app, memory_cache):
    """Changing a user's company access produces a new scoped cache entry."""
    assert _choices_as(app, "cache-user-b") == [("", ""), ("COMP-B", "Company Beta")]

    with app.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cache-user-b")).scalar_one()
        database.session.execute(database.delete(UserCompanyAccess).where(UserCompanyAccess.user_id == user.id))
        database.session.add(UserCompanyAccess(user_id=user.id, company_code="COMP-A"))
        database.session.commit()

    assert _choices_as(app, "cache-user-b") == [("", ""), ("COMP-A", "Company Alpha")]


def test_company_invalidation_refreshes_all_user_entries(app, memory_cache):
    """A namespace generation change refreshes cached results for every user."""
    _choices_as(app, "cache-user-a")
    _choices_as(app, "cache-user-b")

    with app.app_context():
        company = database.session.execute(database.select(Entity).filter_by(code="COMP-A")).scalar_one()
        company.name = "Updated Alpha"
        database.session.commit()
        assert invalidate_cache("companies") is True

    assert _choices_as(app, "cache-user-a") == [("", ""), ("COMP-A", "Updated Alpha")]
    assert _choices_as(app, "cache-user-b") == [("", ""), ("COMP-B", "Company Beta")]
    assert memory_cache.set_calls == 5


def test_entity_disable_route_invalidates_company_choices(app, memory_cache):
    """Disabling a company commits before invalidating cached company choices."""
    assert _choices_as(app, "cache-admin") == [
        ("", ""),
        ("COMP-A", "Company Alpha"),
        ("COMP-B", "Company Beta"),
    ]
    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="cache-admin")).scalar_one()
        company_id = database.session.execute(database.select(Entity.id).filter_by(code="COMP-A")).scalar_one()

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = admin.id
        session["_fresh"] = True

    response = client.get(f"/accounting/entity/set_inactive/{company_id}")

    assert response.status_code == 302
    assert _choices_as(app, "cache-admin") == [("", ""), ("COMP-B", "Company Beta")]


def test_cache_backend_errors_fall_back_to_database(app, memory_cache):
    """A Redis read or write failure does not prevent the database query."""
    memory_cache.fail_get = True
    assert _choices_as(app, "cache-user-a") == [("", ""), ("COMP-A", "Company Alpha")]

    memory_cache.fail_get = False
    memory_cache.fail_set = True
    assert _choices_as(app, "cache-user-b") == [("", ""), ("COMP-B", "Company Beta")]


def test_cache_bypasses_anonymous_and_missing_user_id(app, memory_cache, monkeypatch):
    """The generic decorator never creates a shared anonymous cache entry."""
    import cacao_accounting.cache as cache_module
    from types import SimpleNamespace

    @cache_module.user_scoped_cache("anonymous-test")
    def query():
        return "database result"

    with app.test_request_context("/"):
        assert query() == "database result"
        monkeypatch.setattr(
            cache_module,
            "current_user",
            SimpleNamespace(is_authenticated=True, get_id=lambda: None),
        )
        assert query() == "database result"
    assert memory_cache.set_calls == 0


def test_invalidation_backend_error_is_safe(app, memory_cache):
    """An unavailable cache cannot make a committed database update fail."""
    memory_cache.fail_set = True
    with app.app_context():
        assert invalidate_cache("companies") is False


def test_dummy_cache_and_missing_redis_configuration(app, monkeypatch):
    """The no-extension fallback remains usable and cloud without Redis skips init."""
    from flask import Flask
    import cacao_accounting.cache as cache_module

    dummy = cache_module.DummyCache()
    dummy.init_app(Flask("dummy"))
    dummy.set("key", "value")
    assert dummy.get("key") == "value"
    dummy.delete("key")
    assert dummy.get("key") is None

    monkeypatch.setattr(cache_module, "_has_caching", False)
    assert isinstance(cache_module._crear_cache(), cache_module.DummyCache)
    cloud_app = Flask("cloud_without_redis")
    cloud_app.config["MODO_ESCRITORIO"] = False
    with patch("cacao_accounting.cache.is_desktop_mode", return_value=False):
        cache_module.init_cache(cloud_app)
    assert cloud_app.config["CACHE_TYPE"] == "SimpleCache"


def test_anonymous_and_desktop_requests_bypass_cache(app, memory_cache):
    """Anonymous and desktop contexts execute without reading or writing Redis."""
    with app.test_request_context("/"):
        assert obtener_lista_entidades_por_id_razonsocial() == [("", "")]
    assert memory_cache.set_calls == 0

    app.config["MODO_ESCRITORIO"] = True
    assert _choices_as(app, "cache-user-a") == [("", ""), ("COMP-A", "Company Alpha")]
    assert memory_cache.set_calls == 0


def test_cache_hit_is_logged_only_during_testing(app, memory_cache):
    """The testing mode emits the requested cache-hit diagnostic."""
    import cacao_accounting.cache as cache_module

    _choices_as(app, "cache-user-a")
    with patch("cacao_accounting.config.TESTING_MODE", True), patch.object(cache_module.log, "info") as info:
        _choices_as(app, "cache-user-a")
    info.assert_called_once_with("Cache hit")


@pytest.mark.skipif(
    not TESTING_MODE or not environ.get("CACHE_REDIS_URL"),
    reason="Requires testing mode and a configured Redis service",
)
def test_real_redis_isolates_users_and_invalidates_company_data(app):
    """PostgreSQL and Redis integration preserves user isolation and invalidation."""
    import cacao_accounting.cache as cache_module

    with app.app_context():
        assert cache_module.invalidate_cache("companies") is True

    assert _choices_as(app, "cache-user-a") == [("", ""), ("COMP-A", "Company Alpha")]
    assert _choices_as(app, "cache-user-b") == [("", ""), ("COMP-B", "Company Beta")]

    with app.app_context():
        company = database.session.execute(database.select(Entity).filter_by(code="COMP-A")).scalar_one()
        company.name = "Redis Updated Alpha"
        database.session.commit()
        assert cache_module.invalidate_cache("companies") is True

    assert _choices_as(app, "cache-user-a") == [("", ""), ("COMP-A", "Redis Updated Alpha")]
    assert _choices_as(app, "cache-user-b") == [("", ""), ("COMP-B", "Company Beta")]
