# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1924: las banderas booleanas de entorno se interpretan explícitamente."""

from __future__ import annotations

import pytest

from cacao_accounting.config import configuracion, env_bool


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on", " y "])
def test_valores_verdaderos(monkeypatch, value):
    """Las representaciones verdaderas habituales activan la bandera."""
    monkeypatch.setenv("CACAO_PRUEBA_BOOL", value)
    assert env_bool("CACAO_PRUEBA_BOOL") is True


@pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "off", ""])
def test_valores_falsos(monkeypatch, value):
    """Una cadena no vacía como ``false`` no activa la bandera."""
    monkeypatch.setenv("CACAO_PRUEBA_BOOL", value)
    assert env_bool("CACAO_PRUEBA_BOOL") is False


def test_variable_ausente_usa_el_predeterminado(monkeypatch):
    """Sin variable se respeta el valor por defecto."""
    monkeypatch.delenv("CACAO_PRUEBA_BOOL", raising=False)
    assert env_bool("CACAO_PRUEBA_BOOL") is False
    assert env_bool("CACAO_PRUEBA_BOOL", default=True) is True


def test_tracking_de_sqlalchemy_es_booleano():
    """La configuración no debe pasar la cadena ``'False'`` a Flask-SQLAlchemy."""
    assert configuracion["SQLALCHEMY_TRACK_MODIFICATIONS"] is False
