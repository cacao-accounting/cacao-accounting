# Copyright 2020 William José Moreno Reyes
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
            entity=entidad,
            code=cuenta["codigo"],
            name=cuenta["nombre"],
            group=cuenta["grupo"],
            parent=cuenta["padre"],
            clasification=cuenta["rubro"],
            status="active",
        )
        database.session.add(registro)
        database.session.commit()
