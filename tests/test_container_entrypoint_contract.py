# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Contrato de arranque del contenedor OCI.

Dos fallos impedían que la imagen arrancara:

1. El entrypoint invocaba ``python``, pero la imagen solo instala
   ``python3.12``; el proceso terminaba con exit 127.
2. Caddy corría como ``appuser`` sin ``HOME`` ni directorio propio, por lo que
   no podía crear su configuración/certificados bajo ``/home/appuser``.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ENTRYPOINT = RAIZ / "docker-entry-point.sh"
DOCKERFILE = RAIZ / "Dockerfile"
CADDYFILE = RAIZ / "docs" / "oci_files" / "Caddyfile"


def test_entrypoint_usa_el_binario_python_de_la_imagen():
    """El entrypoint no invoca ``python`` suelto (inexistente en UBI9)."""
    contenido = ENTRYPOINT.read_text(encoding="utf-8")
    assert not re.search(r"(?m)^\s*python\s", contenido), "usa 'python' en vez de python3.12"
    assert "/usr/bin/python3.12" in contenido


def test_dockerfile_define_home_para_caddy():
    """`appuser` tiene HOME y directorio para que Caddy escriba su estado."""
    contenido = DOCKERFILE.read_text(encoding="utf-8")
    assert re.search(r"useradd .*-d /home/appuser", contenido), "falta -d /home/appuser"
    assert "ENV HOME=/home/appuser" in contenido
    # Directorios de Caddy declarados y asignados al usuario no root.
    assert "ENV XDG_CONFIG_HOME=/config" in contenido
    assert "ENV XDG_DATA_HOME=/data" in contenido
    assert re.search(r"chown -R appuser:appuser /config /data", contenido)


def test_caddyfile_montado_y_valido():
    """El Caddyfile se copia a /etc/caddy y declara el proxy al backend."""
    contenido = DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY docs/oci_files/Caddyfile /etc/caddy/Caddyfile" in contenido
    caddy = CADDYFILE.read_text(encoding="utf-8")
    assert ":80" in caddy
    assert "reverse_proxy localhost:8080" in caddy


def test_dockerignore_no_copia_node_modules_local():
    """node_modules se instala en la etapa frontend; no se copia el local."""
    contenido = (RAIZ / ".dockerignore").read_text(encoding="utf-8")
    assert "cacao_accounting/static/node_modules" in contenido


def test_pg8000_pin_es_compatible_con_scramp():
    """pg8000 1.31.5 usa `scramp.make_channel_binding`, eliminado en scramp 1.5.

    El contenedor instala la última scramp (no fijada), por lo que hay que
    fijar pg8000 a una versión que declare `scramp==1.5.0`.
    """
    contenido = DOCKERFILE.read_text(encoding="utf-8")
    assert "pg8000==1.31.5" not in contenido, "pg8000 1.31.5 rompe con scramp 1.5"
    assert "pg8000==1.31.6" in contenido
