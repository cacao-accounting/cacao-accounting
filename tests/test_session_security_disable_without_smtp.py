# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1735: la protección de orígenes puede desactivarse aunque falte SMTP."""

from __future__ import annotations

import pytest

from cacao_accounting.admin.session_security_service import (
    SESSION_SECURITY_KEY,
    is_session_security_enabled,
    set_session_security_enabled,
)
from cacao_accounting.database import CacaoConfig, Modules, database
from cacao_accounting.runtime_mode import is_desktop_mode

CLAVES = (SESSION_SECURITY_KEY, "smtp_server", "smtp_from_email")


def _limpiar(app, previos: dict[str, str]) -> None:
    with app.app_context():
        database.session.execute(database.delete(CacaoConfig).where(CacaoConfig.key.in_(CLAVES)))
        database.session.add_all([CacaoConfig(key=key, value=value) for key, value in previos.items()])
        database.session.commit()


def test_desactiva_proteccion_sin_smtp(app, authenticated_client):
    """Con la protección activa y sin SMTP el formulario permite apagarla."""
    with app.app_context():
        if is_desktop_mode():
            pytest.skip("La ruta de seguridad de sesión no existe en modo Desktop.")
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is None:
            modulo = Modules(module="admin", default=False, enabled=True)
            database.session.add(modulo)
            crear_modulo = True
        else:
            crear_modulo = False
            modulo_anterior = modulo.enabled
            modulo.enabled = True
        filas = database.session.execute(database.select(CacaoConfig).where(CacaoConfig.key.in_(CLAVES))).scalars()
        previos = {fila.key: fila.value for fila in filas}
        database.session.execute(database.delete(CacaoConfig).where(CacaoConfig.key.in_(("smtp_server", "smtp_from_email"))))
        set_session_security_enabled(True)
        database.session.commit()

    try:
        client = authenticated_client("admin")
        pagina = client.get("/settings/session-security")
        assert pagina.status_code == 200
        html = pagina.get_data(as_text=True)
        assert "Guardar" in html
        etiqueta_checkbox = html[html.find('id="enabled"') - 200 : html.find('id="enabled"') + 200]
        assert "disabled" not in etiqueta_checkbox

        response = client.post("/settings/session-security", data={"action": "toggle"}, follow_redirects=True)
        assert response.status_code == 200
        with app.app_context():
            assert is_session_security_enabled() is False
    finally:
        with app.app_context():
            _limpiar(app, previos)
            modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
            if modulo is not None:
                if crear_modulo:
                    database.session.delete(modulo)
                else:
                    modulo.enabled = modulo_anterior
                database.session.commit()
