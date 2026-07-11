# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Pruebas unitarias para el limitador de velocidad (Rate Limiting) y configuración de caché."""

from flask import Flask
from cacao_accounting.limiter import DummyLimiter, init_limiter, _has_limiter
from cacao_accounting.cache import init_cache


def test_dummy_limiter_decorators() -> None:
    """Verifica que DummyLimiter y sus decoradores funcionen correctamente sin arrojar excepciones."""
    dummy = DummyLimiter()

    @dummy.limit("10 per minute")
    def test_func():
        return "hello"

    assert test_func() == "hello"

    @dummy.shared_limit("10 per minute")
    def test_func_shared():
        return "shared"

    assert test_func_shared() == "shared"


def test_init_limiter_desktop_mode() -> None:
    """Verifica que el limitador de velocidad se desactive en modo escritorio."""
    app = Flask("test_app")
    app.config["MODO_ESCRITORIO"] = True

    init_limiter(app)

    if _has_limiter:
        assert app.config.get("RATELIMIT_ENABLED") is False


def test_init_limiter_cloud_mode() -> None:
    """Verifica que el limitador de velocidad se configure correctamente en modo nube."""
    app = Flask("test_app")
    app.config["MODO_ESCRITORIO"] = False
    app.config["CACHE_REDIS_URL"] = "redis://localhost:6379/1"

    init_limiter(app)

    if _has_limiter:
        assert app.config.get("RATELIMIT_ENABLED") is True
        assert app.config.get("RATELIMIT_STORAGE_URI") == "redis://localhost:6379/1"


def test_init_cache_desktop_mode() -> None:
    """Verifica que init_cache configure SimpleCache y remueva Redis en modo escritorio."""
    app = Flask("test_app")
    app.config["MODO_ESCRITORIO"] = True
    app.config["CACHE_REDIS_URL"] = "redis://localhost:6379/0"

    init_cache(app)

    assert app.config.get("CACHE_TYPE") == "SimpleCache"
    assert "CACHE_REDIS_URL" not in app.config


def test_init_cache_cloud_mode() -> None:
    """Verifica que init_cache use Redis en modo nube si está configurado."""
    app = Flask("test_app")
    app.config["MODO_ESCRITORIO"] = False
    app.config["CACHE_REDIS_URL"] = "redis://localhost:6379/0"

    init_cache(app)

    assert app.config.get("CACHE_TYPE") == "RedisCache"
    assert app.config.get("CACHE_REDIS_URL") == "redis://localhost:6379/0"
