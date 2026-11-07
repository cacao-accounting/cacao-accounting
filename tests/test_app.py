# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Humo de arranque: la aplicación se crea, el esquema se materializa y el login responde."""

from __future__ import annotations


def test_import_cacao_accounting():
    """El paquete principal se importa sin errores."""
    import cacao_accounting

    assert cacao_accounting is not None


def test_create_app_y_create_all_funcionan(app):
    """La fixture base crea la app y materializa todas las tablas sin error."""
    from cacao_accounting.database import Entity, database

    with app.app_context():
        entidad = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        assert entidad.company_name == "Cacao Accounting SA"


def test_login_page_responde(client):
    """La ruta publica de login responde (200 o redirect a sí misma)."""
    response = client.get("/login")
    assert response.status_code in {200, 302}


def test_ruta_protegida_redirige_sin_sesion(client):
    """Una ruta autenticada redirige al login cuando no hay sesión."""
    response = client.get("/accounting/")
    assert response.status_code in {302, 401, 403}
    if response.status_code == 302:
        assert "/login" in response.headers["Location"]
