# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1851: la contraseña de PostgreSQL se codifica al componer la URL."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import make_url

from cacao_accounting.config import _database_url_from_environment
from cacao_accounting.database_url import database_url_from_parts

RAIZ = Path(__file__).resolve().parents[1]


def test_caracteres_reservados_sobreviven_a_la_url():
    """@, :, /, % y espacios se codifican y se recuperan al parsear."""
    password = "p@ss:/word con % y espacios"

    url = database_url_from_parts(user="cacao", password=password, host="db", port="5432", name="cacaodb")

    parsed = make_url(url)
    assert parsed.username == "cacao"
    assert parsed.password == password
    assert parsed.database == "cacaodb"


def test_compose_no_interpola_la_contrasena_en_la_uri():
    """Compose entrega componentes y la app compone la URL codificada."""
    compose = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")

    assert "CACAO_DATABASE_URL=postgresql" not in compose
    assert "CACAO_DB_PASSWORD=${DB_PASSWORD" in compose


def test_la_configuracion_compone_la_url_desde_componentes(monkeypatch):
    """config.py acepta CACAO_DB_* como fuente cuando no hay URL explícita."""
    monkeypatch.delenv("CACAO_DATABASE_URL", raising=False)
    monkeypatch.delenv("CACAO_DB", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("CACAO_DB_USER", "cacao")
    monkeypatch.setenv("CACAO_DB_PASSWORD", "clave@segura:2026/01")
    monkeypatch.setenv("CACAO_DB_NAME", "cacaodb")

    parsed = make_url(_database_url_from_environment())

    assert parsed.password == "clave@segura:2026/01"
    assert parsed.username == "cacao"
    assert parsed.database == "cacaodb"
