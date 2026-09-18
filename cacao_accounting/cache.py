# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Soporte para caché de la aplicación adaptándose al modo de ejecución."""

from functools import wraps
from hashlib import sha256
import json
from secrets import token_hex
from typing import Any, Callable, TypeVar
from urllib.parse import quote

from flask import Flask, current_app, has_app_context, has_request_context
from flask_login import current_user

from cacao_accounting.runtime_mode import is_desktop_mode, is_truthy
from cacao_accounting.logs import log

F = TypeVar("F", bound=Callable[..., Any])
# Generation invalidation is immediate after known master-data changes. This
# timeout keeps human Smart Select searches reusable while bounding stale data
# for a future mutation path that has not yet been wired to invalidate.
CACHE_DEFAULT_TIMEOUT = 300

try:
    from flask_caching import Cache

    _has_caching = True
except ImportError:
    _has_caching = False


class DummyCache:
    """Implementación dummy de caché cuando Flask-Caching no está instalado."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Inicializa la caché dummy con un diccionario en memoria."""
        self._data: dict[str, Any] = {}

    def init_app(self, app: Flask) -> None:
        """Inicializa la app con la caché dummy."""
        pass

    def get(self, key: str) -> Any:
        """Obtiene un valor de la caché."""
        return self._data.get(key)

    def set(self, key: str, value: Any, timeout: int = 0) -> None:
        """Guarda un valor en la caché."""
        self._data[key] = value

    def delete(self, key: str) -> None:
        """Elimina un valor de la caché."""
        self._data.pop(key, None)


def _crear_cache() -> Any:
    """Instancia la caché adecuada según la disponibilidad de Flask-Caching."""
    if _has_caching:
        return Cache()
    return DummyCache()


cache = _crear_cache()


def _redis_cache_is_enabled() -> bool:
    """Return whether this request is configured to use Redis in cloud mode."""
    if not _has_caching or not has_app_context() or is_desktop_mode():
        return False
    return bool(
        current_app.config.get("CACHE_REDIS_URL") and str(current_app.config.get("CACHE_TYPE", "")).lower() == "rediscache"
    )


def _generation_key(namespace: str) -> str:
    """Build the Redis key holding a namespace invalidation generation."""
    prefix = current_app.config.get("CACHE_KEY_PREFIX") or "cacao-accounting"
    return f"{prefix}:generation:{quote(namespace, safe='-_')}"


def _build_user_cache_key(namespace: str, user_id: str, generation: str, args: tuple, kwargs: dict) -> str:
    """Build a stable cache key scoped to one user, query, and generation."""
    payload = json.dumps([args, kwargs], sort_keys=True, separators=(",", ":"), default=str)
    query_digest = sha256(payload.encode("utf-8")).hexdigest()
    prefix = current_app.config.get("CACHE_KEY_PREFIX") or "cacao-accounting"
    safe_namespace = quote(namespace, safe="-_")
    safe_user_id = quote(user_id, safe="-_")
    return f"{prefix}:{safe_namespace}:user:{safe_user_id}:generation:{generation}:{query_digest}"


def user_scoped_cache(namespace: str, timeout: int = CACHE_DEFAULT_TIMEOUT) -> Callable[[F], F]:
    """Cache authenticated query results in Redis under the current user's key."""

    def decorate(function: F) -> F:
        @wraps(function)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            if not has_request_context() or not _redis_cache_is_enabled():
                return function(*args, **kwargs)
            if not getattr(current_user, "is_authenticated", False):
                return function(*args, **kwargs)

            user_id = str(current_user.get_id() or "")
            if not user_id:
                return function(*args, **kwargs)

            try:
                generation = str(cache.get(_generation_key(namespace)) or "0")
                key = _build_user_cache_key(namespace, user_id, generation, args, kwargs)
                cached_value = cache.get(key)
            except Exception:
                return function(*args, **kwargs)

            if cached_value is not None:
                from cacao_accounting.config import TESTING_MODE

                if TESTING_MODE:
                    log.info("Cache hit")
                return cached_value

            value = function(*args, **kwargs)
            try:
                cache.set(key, value, timeout=timeout)
            except Exception:
                pass
            return value

        return wrapped  # type: ignore[return-value]

    return decorate


def invalidate_cache(namespace: str) -> bool:
    """Invalidate every user's cached result in one data namespace."""
    if not _redis_cache_is_enabled():
        return False
    try:
        return bool(cache.set(_generation_key(namespace), token_hex(16), timeout=0))
    except Exception:
        log.warning("No se pudo invalidar la caché del espacio {}.", namespace)
        return False


def init_cache(app: Flask) -> None:
    """Inicializa la caché de la aplicación adaptándola al modo de ejecución (escritorio o nube)."""
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
        redis_url = app.config.get("CACHE_REDIS_URL")
        if redis_url:
            app.config["CACHE_TYPE"] = "RedisCache"
            app.config["CACHE_REDIS_URL"] = redis_url
        else:
            app.config["CACHE_TYPE"] = "SimpleCache"

    if not _has_caching:
        return

    cache.init_app(app)
