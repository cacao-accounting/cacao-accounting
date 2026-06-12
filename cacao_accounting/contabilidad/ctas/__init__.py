# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Catalogos de Cuentas Contables."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from collections import namedtuple
from csv import DictReader
from os.path import join

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.config import DIRECTORIO_APP
from cacao_accounting.database import Accounts, database

CatalogoCtas = namedtuple("CatalogoCtas", ["file", "pais", "idioma"])
DIRECTORIO_CTAS = join(DIRECTORIO_APP, "contabilidad", "ctas", "catalogos")

# Inicia deficion de catalogos de cuentas.
base_es = CatalogoCtas(file=join(DIRECTORIO_CTAS, "base_es.csv"), pais=None, idioma="ES")
base_en = CatalogoCtas(file=join(DIRECTORIO_CTAS, "base_en.csv"), pais=None, idioma="EN")
base = base_es

HEADER_ALIASES = {
    "code": ("code", "codigo"),
    "name": ("name", "nombre"),
    "parent": ("parent", "padre"),
    "group": ("group", "grupo"),
    "classification": ("classification", "rubro"),
    "type": ("type", "tipo"),
    "account_type": ("account_type", "tipo_cuenta"),
}


def _value(row: dict[str, str], field: str, default: str = "") -> str:
    for header in HEADER_ALIASES[field]:
        value = row.get(header)
        if value is not None:
            return value.strip()
    return default


def _is_group(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "si", "sí"}


def cargar_catalogos(catalogo, entidad):
    """
    Utilitario para cargar un catalogo de cuentas al sistema.

    Debe ser un archivo .cvs con los encabezados iguales a la base de datos.
    """
    cuentas = DictReader(open(catalogo.file, "r", encoding="utf-8"))
    entity_code = entidad.code if hasattr(entidad, "code") else entidad
    for cuenta in cuentas:
        parent = _value(cuenta, "parent") or None

        registro = Accounts(
            active=True,
            enabled=True,
            entity=entity_code,
            code=_value(cuenta, "code"),
            name=_value(cuenta, "name"),
            group=_is_group(_value(cuenta, "group")),
            parent=parent,
            classification=_value(cuenta, "classification"),
            type_=_value(cuenta, "type") or None,
            account_type=_value(cuenta, "account_type") or None,
            status="active",
        )
        database.session.add(registro)

    session = database.session()
    if not session.in_transaction():
        database.session.commit()
