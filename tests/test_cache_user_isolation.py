"""Integration checks for user-scoped Redis cache behavior."""

from importlib import import_module
from secrets import token_hex

import pytest
from flask_login import current_user, login_user

api_module = import_module("cacao_accounting.api")


@pytest.mark.cache
def test_cached_query_results_are_isolated_between_authenticated_users(app, reference_users, monkeypatch):
    """A cached result for one account must never be returned to another account."""
    if app.config.get("CACHE_TYPE") != "RedisCache" or not app.config.get("CACHE_REDIS_URL"):
        pytest.skip("La prueba de aislamiento requiere Redis configurado en modo Cloud.")

    query = f"cache-isolation-{token_hex(8)}"
    calls: dict[str, int] = {}

    def user_specific_search(*args, **kwargs):
        user_id = str(current_user.get_id())
        calls[user_id] = calls.get(user_id, 0) + 1
        return {"user_id": user_id}

    # Keep the production cache wrapper and replace only its search backend.
    monkeypatch.setattr(api_module, "search_select", user_specific_search)

    def search():
        return api_module._cached_master_data_search("item", query, (), None, ())

    admin_id = str(reference_users["admin"].id)
    reader_id = str(reference_users["reader"].id)

    with app.test_request_context("/"):
        login_user(reference_users["admin"])
        assert search() == {"user_id": admin_id}

    with app.test_request_context("/"):
        login_user(reference_users["reader"])
        assert search() == {"user_id": reader_id}

    with app.test_request_context("/"):
        login_user(reference_users["admin"])
        assert search() == {"user_id": admin_id}

    assert calls == {admin_id: 1, reader_id: 1}
