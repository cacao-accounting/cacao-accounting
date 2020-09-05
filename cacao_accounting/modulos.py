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

from cacao_accounting.database import db, Modulos


contabilidad = {
    "modulo": "accounting",
    "estandar": True,
}
bancos = {
    "modulo": "cash",
    "estandar": True,
}
compras = {
    "modulo": "buying",
    "estandar": True,
}
inventario = {
    "modulo": "inventory",
    "estandar": True,
}
ventas = {
    "modulo": "sales",
    "estandar": True,
}
admin = {
    "modulo": "admin",
    "estandar": True,
}

MODULOS_STANDAR = (
    contabilidad,
    bancos,
    compras,
    inventario,
    ventas,
    admin,
)


def registrar_modulo(modulo):
    """
    Recibe un diccionario y lo inserta en la base de datos.
    """
    registro = Modulos(modulo=modulo["modulo"], estandar=modulo["estandar"], habilitado=modulo["habilitado"])
    db.session.add(registro)
    db.session.commit()


def _init_modulos():
    """
    Inserta en la base de datos los modulos predeterminados del sistema.
    """
    for i in MODULOS_STANDAR:
        i["habilitado"] = True
        registrar_modulo(i)


def modulos():
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
    modulos = {"modulos_activos": list(_modulos_activos), "modulos_inactivos": list(_modulos_inactivos), "modulos": _modulos}
    return modulos


def validar_modulo_activo(modulo):
    """
    Se utiliza en las plantillas para determinar si un modulo se debe presentar o no en la interfas de usuario.
    """
    datos = modulos()
    return modulo in datos["modulos_activos"]
