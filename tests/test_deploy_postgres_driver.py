# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1851: la URI de PostgreSQL del compose declara el driver instalado (psycopg 3)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import make_url

from cacao_accounting.config import _database_url_from_environment

RAIZ = Path(__file__).resolve().parents[1]


def test_compose_declara_driver_psycopg_en_la_uri(monkeypatch):
    """Compose entrega componentes y la aplicación genera la URI con psycopg 3."""
    compose = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
    assert "CACAO_DB_PASSWORD=${DB_PASSWORD" in compose
    assert "CACAO_DB_USER=${DB_USER" in compose
    assert "CACAO_DB_NAME=${DB_NAME" in compose

    monkeypatch.setenv("CACAO_DB_USER", "cacao")
    monkeypatch.setenv("CACAO_DB_PASSWORD", "clave@segura:2026/01")
    monkeypatch.setenv("CACAO_DB_NAME", "cacaodb")
    parsed = make_url(_database_url_from_environment())

    assert parsed.drivername == "postgresql+psycopg"
    assert parsed.password == "clave@segura:2026/01"


def test_compose_requiere_password_y_alinea_healthcheck_con_postgres():
    """La app no arranca con una contraseña DB vacía y el healthcheck respeta la configuración."""
    compose = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")

    assert "${DB_PASSWORD:?DB_PASSWORD must be set}" in compose
    assert 'pg_isready -U \\"$${POSTGRES_USER}\\" -d \\"$${POSTGRES_DB}\\"' in compose
    assert "POSTGRES_USER=${DB_USER:-cacao}" in compose
    assert "POSTGRES_DB=${DB_NAME:-cacaodb}" in compose


def test_la_dependencia_psycopg_declarada_es_la_del_driver():
    """El driver de la URI debe estar en requirements, no solo en la imagen."""
    requirements = (RAIZ / "requirements.txt").read_text(encoding="utf-8")

    assert any(linea.startswith("psycopg") for linea in requirements.splitlines())
