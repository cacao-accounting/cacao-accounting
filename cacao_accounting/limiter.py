# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Módulo para el control de peticiones y prevención de ataques de fuerza bruta (Rate Limiting)."""

from typing import Any, Callable
from flask import Flask

from cacao_accounting.runtime_mode import is_desktop_mode

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    _has_limiter = True
except ImportError:
    _has_limiter = False


class DummyLimiter:
    """Implementación dummy de un limitador de velocidad."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Inicializa el limitador dummy."""
        pass

    def init_app(self, app: Flask) -> None:
        """Inicialización de la aplicación dummy."""
        pass

    def limit(self, limit_value: str, *args: Any, **kwargs: Any) -> Callable[[Any], Any]:
        """Decorador dummy para limitar un endpoint o blueprint."""

        def decorator(f: Any) -> Any:
            return f

        return decorator

    def shared_limit(self, limit_value: str, *args: Any, **kwargs: Any) -> Callable[[Any], Any]:
        """Decorador dummy para un límite compartido."""

        def decorator(f: Any) -> Any:
            return f

        return decorator


def _crear_limiter() -> Any:
    """Instancia el limitador adecuado según la disponibilidad de Flask-Limiter."""
    if _has_limiter:
        return Limiter(
            key_func=get_remote_address,
            storage_uri="memory://",
        )
    return DummyLimiter()


limiter = _crear_limiter()


def init_limiter(app: Flask) -> None:
    """Configura e inicializa el limitador de peticiones en la aplicación."""
    if not _has_limiter:
        return

    # El limitador sólo es necesario cuando no está habilitado el modo escritorio (en la nube)
    desktop = is_desktop_mode()
    enabled = not desktop

    app.config["RATELIMIT_ENABLED"] = enabled

    if enabled:
        storage_uri = app.config.get("RATELIMIT_STORAGE_URI") or app.config.get("CACHE_REDIS_URL") or "memory://"
        app.config["RATELIMIT_STORAGE_URI"] = storage_uri

    limiter.init_app(app)


def rate_limit_blueprint(blueprint: Any, limit_value: str = "60 per minute") -> None:
    """Aplica un límite de velocidad a un Blueprint."""
    if _has_limiter:
        limiter.limit(limit_value)(blueprint)
