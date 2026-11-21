# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2091: `cacaoctl status` distingue configuración de conectividad."""

from __future__ import annotations

import redis

from cacao_accounting.cli import _redis_status


def test_sin_configuracion_no_afirma_conexion():
    assert _redis_status("SimpleCache", None) == "No configurado"


def test_redis_disponible_reporta_conectado(monkeypatch):
    class Client:
        def ping(self):
            return True

    monkeypatch.setattr(redis, "from_url", lambda *_args, **_kwargs: Client())
    assert _redis_status("RedisCache", "redis://localhost:6379/0") == "Conectado"


def test_redis_caido_reporta_no_disponible(monkeypatch):
    class Client:
        def ping(self):
            raise redis.ConnectionError("sin servidor")

    monkeypatch.setattr(redis, "from_url", lambda *_args, **_kwargs: Client())
    assert _redis_status("RedisCache", "redis://localhost:6379/0") == "No disponible"
