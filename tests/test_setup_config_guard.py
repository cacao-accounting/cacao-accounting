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
        with pytest.raises(ValueError, match="servicio auditado"):
            database.session.execute(statement)
        database.session.rollback()
        database.session.remove()
        database.engine.dispose()
