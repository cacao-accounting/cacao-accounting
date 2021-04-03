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
#
# Contributors:
# - William José Moreno Reyes

from collections import namedtuple
from csv import DictReader
from os.path import join
from cacao_accounting.database import db, Cuentas
from cacao_accounting.tools import home


CatalogoCtas = namedtuple("CatalogoCtas", ["file", "pais", "idioma"])
dir_ctas = join(home, "contabilidad", "ctas", "catalogos")

# Inicia deficion de catalogos de cuentas.
base = CatalogoCtas(file=join(dir_ctas, "base.csv"), pais=None, idioma="ES")
desarrollo = CatalogoCtas(file=join(dir_ctas, "base-dev.csv"), pais=None, idioma="ES")


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

        registro = Cuentas(
            activa=True,
            habilitada=True,
            entidad=entidad,
            codigo=cuenta["codigo"],
            nombre=cuenta["nombre"],
            grupo=cuenta["grupo"],
            padre=cuenta["padre"],
            rubro=cuenta["rubro"],
            tipo=cuenta["tipo"],
            status="activa",
        )
        db.session.add(registro)
        db.session.commit()
