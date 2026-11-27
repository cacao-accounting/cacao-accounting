# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1679 y #2270: `User.token` degrada sin caché y conserva la revocación persistida."""

from __future__ import annotations

import hashlib

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
        assert usuario.api_token_hash == hashlib.sha256(b"token-nuevo").hexdigest()


def test_token_sin_valor_volatil_devuelve_none_si_la_cache_falla(app, reference_users, monkeypatch):
    """El getter degrada a None cuando solo existe la caché rota."""
    monkeypatch.setattr(cache_module, "cache", _CacheRoto())
    with app.app_context():
        usuario = database.session.get(User, reference_users["admin"].id)
        usuario._token_volatile = None

        assert usuario.token is None


def test_huella_del_token_autoriza_otra_sesion_sin_cache(entorno_contable_aislado, monkeypatch):
    """Una instancia nueva reconoce el JWT aunque la caché esté caída."""
    application = entorno_contable_aislado.app
    monkeypatch.setattr(cache_module, "cache", _CacheRoto())
    with application.app_context():
        usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        usuario.token = "token-de-la-sesion-anterior"
        database.session.commit()

    with application.app_context():
        otra_instancia = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        assert otra_instancia.token is None
        assert otra_instancia.token_matches("token-de-la-sesion-anterior") is True
        assert otra_instancia.token_matches("token-obsoleto") is False
        assert "token-de-la-sesion-anterior" not in (otra_instancia.api_token_hash or "")


def test_limpiar_token_revoca_la_huella_persistida(entorno_contable_aislado, monkeypatch):
    """El cierre de sesión elimina la huella aunque falle la caché."""
    application = entorno_contable_aislado.app
    monkeypatch.setattr(cache_module, "cache", _CacheRoto())
    with application.app_context():
        usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        usuario.token = "token-a-revocar"
        database.session.commit()
        assert usuario.token_matches("token-a-revocar") is True

        usuario.token = None
        database.session.commit()

    with application.app_context():
        otra_instancia = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        assert otra_instancia.api_token_hash is None
        assert otra_instancia.token_matches("token-a-revocar") is False


class _CacheConTokenViejo:
    """Caché que sigue devolviendo un JWT ya sustituido."""

    def get(self, _key):
        return "token-viejo"

    def set(self, _key, _value, timeout=0):
        return None

    def delete(self, _key):
        return None


def test_cache_obsoleta_no_revalida_token_revocado(app, reference_users, monkeypatch):
    """La huella persistida prevalece sobre un valor volátil o de caché viejo."""
    monkeypatch.setattr(cache_module, "cache", _CacheConTokenViejo())
    with app.app_context():
        usuario = database.session.get(User, reference_users["admin"].id)
        usuario.token = "token-nuevo"
        assert usuario.token_matches("token-nuevo") is True
        assert usuario.token_matches("token-viejo") is False


def test_filas_legacy_sin_huella_requieren_nuevo_login(app, reference_users):
    """Sin huella persistida no se autoriza un JWT aunque exista valor volátil."""
    with app.app_context():
        usuario = database.session.get(User, reference_users["admin"].id)
        usuario.api_token_hash = None
        usuario._token_volatile = "token-legacy"
        database.session.commit()

        assert usuario.token_matches("token-legacy") is False


def test_tokens_del_mismo_segundo_son_distintos_y_revocan_el_anterior(app, reference_users, monkeypatch):
    """#2270: logout y login en el mismo segundo no reactivan el JWT cerrado."""
    from datetime import datetime, timezone

    from cacao_accounting.api import _identity_for_api_token
    from cacao_accounting.auth import helpers as auth_helpers

    instante = datetime.now(timezone.utc).replace(microsecond=0)
    monkeypatch.setattr(auth_helpers, "_utcnow", lambda: instante)
    with app.app_context():
        usuario = database.session.get(User, reference_users["admin"].id)
        auth_helpers.asignar_token_para_usuario(usuario)
        primer_token = usuario.token
        usuario.token = None
        database.session.commit()

        auth_helpers.asignar_token_para_usuario(usuario)
        segundo_token = usuario.token

        assert primer_token != segundo_token
        assert usuario.token_matches(primer_token) is False
        assert usuario.token_matches(segundo_token) is True
        assert _identity_for_api_token(primer_token) is None
        assert _identity_for_api_token(segundo_token).id == usuario.id
