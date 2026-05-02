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
base = CatalogoCtas(file=join(DIRECTORIO_CTAS, "base.csv"), pais=None, idioma="ES")


def cargar_catalogos(catalogo, entidad):
    """
    Utilitario para cargar un catalogo de cuentas al sistema.

    Debe ser un archivo .cvs con los encabezados iguales a la base de datos.
    """
    cuentas = DictReader(open(catalogo.file, "r", encoding="utf-8"))
    entity_code = entidad.code if hasattr(entidad, "code") else entidad
    for cuenta in cuentas:
        if cuenta["grupo"] == "1":
            cuenta["grupo"] = True
        else:
            cuenta["grupo"] = False

        if cuenta["padre"] == "":
            cuenta["padre"] = None

        registro = Accounts(
            active=True,
            enabled=True,
            entity=entity_code,
            code=cuenta["codigo"],
            name=cuenta["nombre"],
            group=cuenta["grupo"],
            parent=cuenta["padre"],
            clasification=cuenta["rubro"],
            status="active",
        )
        database.session.add(registro)

    session = database.session()
    if not session.in_transaction():
        database.session.commit()
