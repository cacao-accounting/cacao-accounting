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


def test_driver_postgresql_es_psycopg_compilado():
    """El driver PostgreSQL por defecto es psycopg 3 con extensión C.

    Se compila en un paso explícito (requiere `pg_config` de `libpq-devel`) y
    se verifica el backend `c`; la libpq queda disponible en runtime.
    """
    contenido = DOCKERFILE.read_text(encoding="utf-8")
    for legacy in ("pg8000", "psycopg2"):
        assert legacy not in contenido, f"{legacy} ya no es el driver soportado"
    assert "libpq-devel" in contenido, "falta libpq-devel para compilar psycopg"
    assert "--no-binary psycopg-c" in contenido, "falta forzar la compilación desde sdist"
    assert "psycopg[c]==3.3.9" in contenido
    assert "pq.__impl__ == 'c'" in contenido, "falta la verificación del backend C"
    # purelib (lib) y platlib (lib64) se copian ambos: la extensión C reside en lib64.
    assert "/install/lib64/python3.12/site-packages /usr/lib64/python3.12/site-packages" in contenido
    # libpq en runtime para la extensión compilada.
    runtime = contenido.split("FROM registry.access.redhat.com/ubi9/ubi-minimal:9.8-1782797275\n", 1)[-1]
    assert "libpq" in runtime
