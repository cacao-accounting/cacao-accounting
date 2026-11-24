# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1679: `User.token` funciona con Redis configurado pero inaccesible."""

from __future__ import annotations

from cacao_accounting import cache as cache_module
from cacao_accounting.database import User, database


class _CacheNoDisponible(Exception):
    """Error de conexión de caché que no hereda de OSError."""


class _CacheRoto:
    """Doble de caché que simula Redis caído en get/set/delete."""

    def get(self, _key):
        raise _CacheNoDisponible("redis caído")

    def set(self, _key, _value, timeout=0):
        raise _CacheNoDisponible("redis caído")

    def delete(self, _key):
        raise _CacheNoDisponible("redis caído")


def test_token_usa_fallback_volatil_si_la_cache_falla(app, reference_users, monkeypatch):
    """Get y set no propagan el error de conexión y conservan el valor volátil."""
    monkeypatch.setattr(cache_module, "cache", _CacheRoto())
    with app.app_context():
        usuario = database.session.get(User, reference_users["admin"].id)
        usuario._token_volatile = "token-volatil"

        assert usuario.token == "token-volatil"

        usuario.token = "token-nuevo"

        assert usuario._token_volatile == "token-nuevo"
        assert usuario.token == "token-nuevo"


def test_token_sin_valor_volatil_devuelve_none_si_la_cache_falla(app, reference_users, monkeypatch):
    """El getter degrada a None cuando solo existe la caché rota."""
    monkeypatch.setattr(cache_module, "cache", _CacheRoto())
    with app.app_context():
        usuario = database.session.get(User, reference_users["admin"].id)
        usuario._token_volatile = None

        assert usuario.token is None
