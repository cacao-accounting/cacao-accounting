# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Soporte para caché de la aplicación adaptándose al modo de ejecución."""

from typing import Any
from flask import Flask
from cacao_accounting.runtime_mode import is_desktop_mode, is_truthy

try:
    from flask_caching import Cache

    _has_caching = True
except ImportError:
    _has_caching = False


class DummyCache:
    """Implementación dummy de caché cuando Flask-Caching no está instalado."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Inicializa la caché dummy."""
        pass

    def init_app(self, app: Flask) -> None:
        """Inicializa la app con la caché dummy."""
        pass


def _crear_cache() -> Any:
    """Instancia la caché adecuada según la disponibilidad de Flask-Caching."""
    if _has_caching:
        return Cache()
    return DummyCache()


cache = _crear_cache()


def init_cache(app: Flask) -> None:
    """Inicializa la caché de la aplicación adaptándola al modo de ejecución (escritorio o nube)."""
    if not _has_caching:
        return

    if "MODO_ESCRITORIO" in app.config:
        desktop = is_truthy(app.config.get("MODO_ESCRITORIO"))
    else:
        desktop = is_desktop_mode()

    if desktop:
        # En modo escritorio, forzamos SimpleCache para no requerir un servidor Redis local
        app.config["CACHE_TYPE"] = "SimpleCache"
        app.config.pop("CACHE_REDIS_URL", None)
    else:
        # En modo nube/servidor, usamos Redis si está configurado
        redis_url = app.config.get("CACHE_REDIS_URL") or app.config.get("REDIS_URL")
        if redis_url:
            app.config["CACHE_TYPE"] = "RedisCache"
            app.config["CACHE_REDIS_URL"] = redis_url
        else:
            app.config["CACHE_TYPE"] = "SimpleCache"

    cache.init_app(app)
