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

"""
Intefaz para el control de los modulos del sistema.

Un modulo puede ser estandar o un añadido, todo modulo debe definir un blueprint.
"""

from pkgutil import iter_modules
from typing import Union
from flask import Flask
from cacao_accounting.database import database, Modulos


contabilidad = {
    "modulo": "accounting",
    "estandar": True,
    "habilitado": True,
}
bancos = {
    "modulo": "cash",
    "estandar": True,
    "habilitado": True,
}
compras = {
    "modulo": "purchases",
    "estandar": True,
    "habilitado": True,
}
inventario = {
    "modulo": "inventory",
    "estandar": True,
    "habilitado": True,
}
ventas = {
    "modulo": "sales",
    "estandar": True,
    "habilitado": True,
}
admin = {
    "modulo": "admin",
    "estandar": True,
    "habilitado": True,
}

MODULOS_STANDAR = [
    contabilidad,
    bancos,
    compras,
    inventario,
    ventas,
    admin,
]

MODULOS_ADICIONALES = None
modulos = iter_modules()
for modulo in modulos:
    MODULO_COMO_TEXTO = str(modulo.name)
    try:
        if MODULO_COMO_TEXTO.startswith("cacao_accounting_modulo"):
            MODULOS_ADICIONALES = []
            MODULOS_ADICIONALES.append(MODULO_COMO_TEXTO)
    except AttributeError:
        pass


def registrar_modulo(entrada: dict) -> None:
    """Recibe un diccionario y lo inserta en la base de datos."""
    registro = Modulos(modulo=entrada["modulo"], estandar=entrada["estandar"], habilitado=entrada["habilitado"])
    # pylint: disable=E1101
    database.session.add(registro)
    database.session.commit()


def _init_modulos() -> None:
    """Inserta en la base de datos los modulos predeterminados del sistema."""
    for i in MODULOS_STANDAR:
        i["ruta"] = None
        registrar_modulo(i)


def listado_modulos() -> dict:
    """
    Devuelve listado de modulos instalados en dos listas.

    - Una para modulos habilitados.
    - Una para modulos deshabilitados.
    """
    _modulos = Modulos.query.order_by(Modulos.id).all()
    _modulos_activos = []
    _modulos_inactivos = []
    for i in _modulos:
        if i.habilitado is True:
            _modulos_activos.append(i.modulo)
        else:
            _modulos_inactivos.append(i.modulo)
    lista_modulos = {
        "modulos_activos": list(_modulos_activos),
        "modulos_inactivos": list(_modulos_inactivos),
        "modulos": list(_modulos),
    }
    return lista_modulos


def validar_modulo_activo(modulo_a_validar: str) -> bool:
    """Valida si el modulo se encuentra activo."""
    datos = listado_modulos()
    return modulo_a_validar in datos["modulos_activos"]


def registrar_modulos_adicionales(flaskapp: Flask) -> None:
    """
    Registra los blueprints definidos en el modulo.

    Referencias:
     - https://flask.palletsprojects.com/en/1.1.x/blueprints/
    """
    from importlib import import_module

    if MODULOS_ADICIONALES:
        modulos_extra: Union[list, None] = []
        for i in MODULOS_ADICIONALES:
            paquete = import_module(i)
            flaskapp.register_blueprint(paquete.blueprint)  # type: ignore[attr-defined]
            modulos_extra.append(paquete)  # type: ignore[union-attr]
    else:
        modulos_extra = None
    flaskapp.add_template_global(modulos_extra, "modulos_extra")  # type: ignore[arg-type]
