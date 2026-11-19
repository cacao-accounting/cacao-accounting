# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2256: la configuración del asistente funciona con el guard ICFR activo."""

from __future__ import annotations

import pytest
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.config_values import set_config_value
from cacao_accounting.database import CacaoConfig, database
from cacao_accounting.internal_control_service import config_value_transition


def _app():
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )


def test_set_config_value_escribe_con_el_guard_activo():
    """El escritor auditado del setup no es rechazado por el guard."""
    app = _app()
    with app.app_context():
        database.create_all()
        set_config_value("SETUP_LANGUAGE", "en")
        database.session.commit()
        assert (
            database.session.execute(database.select(CacaoConfig.value).filter_by(key="SETUP_LANGUAGE")).scalar_one() == "en"
        )
        database.session.remove()
        database.engine.dispose()


def test_insercion_core_directa_sigue_bloqueada():
    """El contexto no abre una vía genérica para Core."""
    app = _app()
    with app.app_context():
        database.create_all()
        statement = sqlite_insert(CacaoConfig.__table__).values(id="X", key="OTRA", value="1")
        with pytest.raises(ValueError, match="(servicio auditado|audited service)"):
            database.session.execute(statement)
        database.session.rollback()
        database.session.remove()
        database.engine.dispose()


def test_config_value_transition_no_autoriza_otra_clave():
    """El contexto autoriza solo la clave indicada, no cualquier configuración."""
    app = _app()
    with app.app_context():
        database.create_all()
        with config_value_transition("SETUP_LANGUAGE"):
            set_config_value("SETUP_LANGUAGE", "en")
            database.session.commit()
            statement = sqlite_insert(CacaoConfig.__table__).values(id="Y", key="SMTP_PASSWORD", value="1")
            with pytest.raises(ValueError, match="(servicio auditado|audited service)"):
                database.session.execute(statement)
            database.session.rollback()
        filas = database.session.execute(database.select(CacaoConfig.key, CacaoConfig.value)).all()
        assert filas == [("SETUP_LANGUAGE", "en")]
        database.session.remove()
        database.engine.dispose()


def test_contexto_config_value_no_se_fuga_al_salir():
    """La autorización se retira al cerrar el contexto, aunque sea la misma clave."""
    app = _app()
    with app.app_context():
        database.create_all()
        with config_value_transition("SETUP_LANGUAGE"):
            set_config_value("SETUP_LANGUAGE", "en")
            database.session.commit()
        statement = sqlite_insert(CacaoConfig.__table__).values(id="Z", key="SETUP_LANGUAGE", value="es")
        with pytest.raises(ValueError, match="(servicio auditado|audited service)"):
            database.session.execute(statement)
        database.session.rollback()
        assert (
            database.session.execute(database.select(CacaoConfig.value).filter_by(key="SETUP_LANGUAGE")).scalar_one() == "en"
        )
        database.session.remove()
        database.engine.dispose()


def test_set_config_value_actualiza_clave_existente_con_guard_activo():
    """El upsert sobre una clave existente también pasa por el escritor auditado."""
    app = _app()
    with app.app_context():
        database.create_all()
        set_config_value("SETUP_LANGUAGE", "en")
        database.session.commit()
        identificador = database.session.execute(database.select(CacaoConfig.id).filter_by(key="SETUP_LANGUAGE")).scalar_one()
        set_config_value("SETUP_LANGUAGE", "es")
        database.session.commit()
        filas = database.session.execute(
            database.select(CacaoConfig.id, CacaoConfig.value).filter_by(key="SETUP_LANGUAGE")
        ).all()
        assert filas == [(identificador, "es")]
        database.session.remove()
        database.engine.dispose()


def test_config_value_transition_multiclave():
    """Varias claves declaradas se autorizan, pero una tercera sigue bloqueada."""
    app = _app()
    with app.app_context():
        database.create_all()
        with config_value_transition("SETUP_LANGUAGE", "SETUP_COUNTRY"):
            valores = {"SETUP_LANGUAGE": "es", "SETUP_COUNTRY": "NI"}
            for clave, valor in valores.items():
                database.session.execute(sqlite_insert(CacaoConfig.__table__).values(id=f"M-{clave}", key=clave, value=valor))
            database.session.commit()
            statement = sqlite_insert(CacaoConfig.__table__).values(id="M-OTRA", key="SMTP_PASSWORD", value="1")
            with pytest.raises(ValueError, match="(servicio auditado|audited service)"):
                database.session.execute(statement)
            database.session.rollback()
        claves = set(database.session.execute(database.select(CacaoConfig.key)).scalars().all())
        assert claves == {"SETUP_LANGUAGE", "SETUP_COUNTRY"}
        database.session.remove()
        database.engine.dispose()
