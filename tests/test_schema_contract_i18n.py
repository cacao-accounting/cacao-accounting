# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1898: el contrato de esquema conserva sus mensajes traducibles intactos."""

from __future__ import annotations

import gettext
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
LOCALES = RAIZ / "cacao_accounting" / "translations"
# Los dos módulos que definen la máquina de estados y su exposición en consola.
MODULOS = (RAIZ / "cacao_accounting" / "database" / "helpers.py", RAIZ / "cacao_accounting" / "cli.py")
# Un acento sustituido por ``?`` convierte el msgid en una clave nueva: el catálogo
# devuelve el español y el usuario angloparlante ve el mojibake sin ningún error.
MENSAJES_ESQUEMA = {
    'Revisión destino (por defecto: head).': 'Target revision (default: head).',
    'Revisión específica a aplicar.': 'Specific revision to apply.',
    'Inserta datos de ejemplo después de crear la base.': 'Insert example data after creating the database.',
    'La base de datos existente será reemplazada.': 'The existing database will be replaced.',
    'Se están usando usuario y contraseña predeterminados para el setup inicial.': 'Default username and password are being used for initial setup.',
    "La base de datos no está inicializada; ejecute primero 'cacaoctl db init'.": "The database is not initialized; run 'cacaoctl db init' first.",
    'La base de datos tiene un esquema parcial o inconsistente; restaure un respaldo o inicialice una base nueva.': 'The database has a partial or inconsistent schema; restore a backup or initialize a new database.',
    "La base de datos no tiene historial Alembic; ejecute 'cacaoctl db migrate' para registrar la revisión compatible.": "The database has no Alembic history; run 'cacaoctl db migrate' to register the compatible revision.",
    "La base de datos requiere migraciones; ejecute 'cacaoctl db migrate' antes de servir.": "The database requires migrations; run 'cacaoctl db migrate' before serving.",
    'El estado del esquema de base de datos no es compatible: %(status)s': 'The database schema state is not compatible: %(status)s',
    'No hay migraciones pendientes.': 'No pending migrations.',
    'Migraciones aplicadas correctamente.': 'Migrations applied successfully.',
    'No fue posible aplicar las migraciones: %(error)s': 'Could not apply migrations: %(error)s',
}
MOJIBAKE = re.compile(r"[A-Za-z]\?[A-Za-z]")


def _catalogo_ingles() -> gettext.NullTranslations:
    """Carga el binario de inglés que consume la app en tiempo de ejecución."""
    return gettext.translation("messages", localedir=str(LOCALES), languages=["en"])


def test_fuentes_del_contrato_de_esquema_sin_acentos_perdidos():
    """Ningún módulo del contrato puede reintroducir una palabra con ``?``."""
    for modulo in MODULOS:
        lineas = modulo.read_text(encoding="utf-8").splitlines()
        for numero, linea in enumerate(lineas, start=1):
            assert not MOJIBAKE.search(linea), f"{modulo.name}:{numero}: {linea.strip()}"


def test_mensajes_de_esquema_tienen_traduccion_inglesa():
    """Los seis msgids del asistente y de ``db migrate`` se resuelven en inglés."""
    catalogo = _catalogo_ingles()
    for msgid, esperado in MENSAJES_ESQUEMA.items():
        assert catalogo.gettext(msgid) == esperado, msgid


def test_msgid_corrupto_se_devuelve_crudo():
    """Control de la guarda: la variante sin acentos no existe en el catálogo."""
    catalogo = _catalogo_ingles()
    corrupto = "Revisi?n destino (por defecto: head)."
    assert catalogo.gettext(corrupto) == corrupto
