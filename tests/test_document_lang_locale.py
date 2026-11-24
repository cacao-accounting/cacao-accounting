# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1918: el atributo lang del documento sigue el locale efectivo de Babel.

El perfil autenticado usa el idioma del usuario y las páginas públicas el
idioma de configuración; ambos deben coincidir con lo que Flask-Babel traduce.
"""

from __future__ import annotations

from cacao_accounting.database import CacaoConfig, User, database
from cacao_accounting.setup.repository import set_setup_value
from cacao_accounting.setup.service import SETUP_LANGUAGE


def test_perfil_usa_el_idioma_del_usuario(app, authenticated_client, reference_users):
    """Con User.language=en el documento declara lang=en."""
    user_id = str(reference_users["admin"].id)
    with app.app_context():
        usuario = database.session.get(User, user_id)
        anterior = usuario.language
        usuario.language = "en"
        database.session.commit()
    try:
        response = authenticated_client("admin").get("/auth/profile")
    finally:
        with app.app_context():
            usuario = database.session.get(User, user_id)
            usuario.language = anterior
            database.session.commit()

    assert response.status_code == 200
    assert '<html lang="en">' in response.get_data(as_text=True)


def test_paginas_publicas_usan_el_idioma_de_configuracion(app):
    """Login y recuperación declaran el idioma configurado en setup."""
    anterior = None
    with app.app_context():
        fila = database.session.execute(database.select(CacaoConfig).filter_by(key=SETUP_LANGUAGE)).scalar_one_or_none()
        anterior = fila.value if fila is not None else None
        set_setup_value(SETUP_LANGUAGE, "en")
        database.session.commit()
    try:
        client = app.test_client()
        for ruta in ("/login", "/auth/forgot-password"):
            response = client.get(ruta)
            assert response.status_code == 200, ruta
            assert '<html lang="en">' in response.get_data(as_text=True), ruta
    finally:
        with app.app_context():
            database.session.execute(database.delete(CacaoConfig).where(CacaoConfig.key == SETUP_LANGUAGE))
            if anterior is not None:
                database.session.add(CacaoConfig(key=SETUP_LANGUAGE, value=anterior))
            database.session.commit()
