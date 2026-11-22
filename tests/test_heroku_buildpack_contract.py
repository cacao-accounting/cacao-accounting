# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Contrato del despliegue con buildpacks de Heroku.

El buildpack de Python solo instala las dependencias de ``requirements.txt``.
Por eso el despliegue necesita, además del Procfile, un hook ``post_compile``
que instale el paquete (y el comando ``cacaoctl`` usado en el Procfile), los
assets estáticos y los catálogos de traducción; y un ``Aptfile`` con las
bibliotecas de sistema de WeasyPrint, libmagic y libpq.
"""

from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PROCFILE = RAIZ / "Procfile"
APTFILE = RAIZ / "Aptfile"
APP_JSON = RAIZ / "app.json"
POST_COMPILE = RAIZ / "bin" / "post_compile"
PYTHON_VERSION = RAIZ / ".python-version"
SLUGIGNORE = RAIZ / ".slugignore"


def _procesos() -> dict[str, str]:
    """Lee el Procfile como un mapa tipo de proceso → comando."""
    procesos: dict[str, str] = {}
    for linea in PROCFILE.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or ":" not in linea:
            continue
        tipo, comando = linea.split(":", 1)
        procesos[tipo.strip()] = comando.strip()
    return procesos


def test_procfile_declara_web_y_release():
    """`web` sirve la aplicación y `release` prepara la base antes del despliegue."""
    procesos = _procesos()
    assert procesos["web"] == "python -m cacao_accounting"
    assert "db init" in procesos["release"]
    assert "db migrate" in procesos["release"]


def test_version_de_python_soportada_por_el_buildpack():
    """El buildpack exige una versión declarada explícitamente."""
    version = PYTHON_VERSION.read_text(encoding="utf-8").strip()
    assert version.count(".") == 1, "se recomienda la forma mayor.menor para recibir parches"
    mayor, menor = (int(parte) for parte in version.split("."))
    assert (mayor, menor) >= (3, 12), "cacao_accounting requiere Python >= 3.12"


def test_aptfile_incluye_las_bibliotecas_de_sistema():
    """WeasyPrint, libmagic y la compilación de psycopg requieren paquetes apt."""
    paquetes = {
        linea.strip()
        for linea in APTFILE.read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.strip().startswith("#")
    }
    for requerido in (
        "libmagic1",
        "libpq-dev",
        "libpango-1.0-0",
        "libpangoft2-1.0-0",
        "libharfbuzz-subset0",
        "nodejs",
        "npm",
    ):
        assert requerido in paquetes, f"falta {requerido} en Aptfile"


def test_post_compile_instala_paquete_assets_y_traducciones():
    """El hook completa el slug con lo que el buildpack de Python no instala."""
    contenido = POST_COMPILE.read_text(encoding="utf-8")
    assert "'.[cloud]'" in contenido, "falta instalar el paquete con el extra cloud"
    assert "npm ci" in contenido, "faltan los assets estáticos"
    assert "write_mo" in contenido, "faltan los catálogos de traducción compilados"
    assert "set -euo pipefail" in contenido, "el hook debe abortar el build ante un error"


def test_app_json_declara_buildpacks_y_variables_requeridas():
    """`app.json` permite desplegar con un clic y documenta la configuración."""
    manifesto = json.loads(APP_JSON.read_text(encoding="utf-8"))
    urls = [buildpack["url"] for buildpack in manifesto["buildpacks"]]
    assert urls == ["heroku-community/apt", "heroku/python"], "apt debe ejecutarse antes que python"
    assert "web" in manifesto["formation"]
    assert manifesto["env"]["CACAO_USER"]["required"] is True
    assert manifesto["env"]["CACAO_PSWD"]["required"] is True
    assert "DATABASE" in {addon["as"] for addon in manifesto["addons"]}


def test_slugignore_excluye_un_segundo_gestor_de_dependencias():
    """El buildpack aborta si encuentra requirements.txt y uv.lock a la vez."""
    contenido = SLUGIGNORE.read_text(encoding="utf-8")
    assert "uv.lock" in contenido
    assert "/tests" in contenido.replace("tests/", "/tests")
