# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1851: la URI de PostgreSQL del compose declara el driver instalado (psycopg 3)."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_compose_declara_driver_psycopg_en_la_uri():
    """Sin driver explícito SQLAlchemy busca psycopg2, que la imagen no instala."""
    compose = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
    lineas = [linea for linea in compose.splitlines() if "CACAO_DATABASE_URL" in linea]

    assert lineas, "docker-compose.yml no define CACAO_DATABASE_URL"
    assert any("postgresql+psycopg://" in linea for linea in lineas)


def test_la_dependencia_psycopg_declarada_es_la_del_driver():
    """El driver de la URI debe estar en requirements, no solo en la imagen."""
    requirements = (RAIZ / "requirements.txt").read_text(encoding="utf-8")

    assert any(linea.startswith("psycopg") for linea in requirements.splitlines())
