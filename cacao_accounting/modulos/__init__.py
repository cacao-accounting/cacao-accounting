# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""
Intefaz para el control de los modulos del sistema.

Un modulo puede ser estandar o un añadido, todo modulo debe definir un blueprint.
"""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# ---------------------------------------------------------------------------------------
from pkgutil import iter_modules
from typing import Any

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Flask

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.database import Modules, database

# <---------------------------------------------------------------------------------------------> #
# Módulos base del sistema e incluidos en el repositorio principal.
# Módulos adicionales se deben declarar como paquetes adicionales.
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

# <---------------------------------------------------------------------------------------------> #
# Interface para agregar módulos adicionales al sistema.
modulos_adicionales_detectados: list[str] = []
modulos = iter_modules()
for modulo in modulos:
    MODULO_COMO_TEXTO = str(modulo.name)
    try:
        if MODULO_COMO_TEXTO.startswith("cacao_accounting_modulo") or MODULO_COMO_TEXTO.startswith("cacao_accounting_module"):
            modulos_adicionales_detectados.append(MODULO_COMO_TEXTO)
    except AttributeError:
        pass

MODULOS_ADICIONALES: list[str] | None = modulos_adicionales_detectados or None


# <---------------------------------------------------------------------------------------------> #
# Funciones auxiliares para la administración de módulos.


def _parse_plugin_module_name(package_name: str) -> str:
    """Extrae el nombre lógico del modulo a partir del paquete detectado."""
    if package_name.startswith("cacao_accounting_modulo_"):
        return package_name.removeprefix("cacao_accounting_modulo_")
    if package_name.startswith("cacao_accounting_module_"):
        return package_name.removeprefix("cacao_accounting_module_")
    return package_name


def registrar_modulo(entrada: dict) -> None:
    """Recibe un diccionario y lo inserta en la base de datos."""
    registro = Modules(
        module=entrada["modulo"],
        default=entrada["estandar"],
        enabled=entrada["habilitado"],
    )
    database.session.add(registro)
    database.session.commit()


def init_modulos() -> None:
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
    _modulos = Modules.query.order_by(Modules.id).all()
    _modulos_activos = []
    _modulos_inactivos = []
    for i in _modulos:
        if i.enabled is True:
            _modulos_activos.append(i.module)
        else:
            _modulos_inactivos.append(i.module)
    lista_modulos = {
        "modulos_activos": list(_modulos_activos),
        "modulos_inactivos": list(_modulos_inactivos),
        "modulos": list(_modulos),
    }
    return lista_modulos


def obtener_modulos_disponibles() -> list[dict[str, Any]]:
    """Devuelve los módulos estándar y plugins detectados en el entorno."""
    disponibles: list[dict[str, Any]] = []
    for modulo in MODULOS_STANDAR:
        disponibles.append(
            {
                "module": modulo["modulo"],
                "default": modulo["estandar"],
                "type": "estandar",
                "package": None,
            }
        )

    if MODULOS_ADICIONALES:
        for paquete in MODULOS_ADICIONALES:
            disponibles.append(
                {
                    "module": _parse_plugin_module_name(paquete),
                    "default": False,
                    "type": "plugin",
                    "package": paquete,
                }
            )

    return disponibles


def sincronizar_modulos() -> dict:
    """Asegura que los módulos detectados estén registrados en la base de datos."""
    modulos_existentes = {registro.module for registro in Modules.query.all()}

    for modulo in MODULOS_STANDAR:
        if modulo["modulo"] not in modulos_existentes:
            registrar_modulo(modulo)

    if MODULOS_ADICIONALES:
        for paquete in MODULOS_ADICIONALES:
            moduloname = _parse_plugin_module_name(paquete)
            if moduloname not in modulos_existentes:
                registrar_modulo({"modulo": moduloname, "estandar": False, "habilitado": False})

    return listado_modulos()


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
        modulos_extra_list: list[Any] = []
        for i in MODULOS_ADICIONALES:
            paquete = import_module(i)
            flaskapp.register_blueprint(paquete.blueprint)
            modulos_extra_list.append(paquete)
        modulos_extra: list[Any] | None = modulos_extra_list
    else:
        modulos_extra = None
    flaskapp.jinja_env.globals["modulos_extra"] = modulos_extra


def lista_tipos_documentos() -> list:
    """Devuelve listado de documentos."""
    DOCUMENTOS = [
        ("journal", "Comprobante de Diario"),
        ("sales-invoice", "Factura de Venta"),
        ("purchase-invoice", "Factura de Compra"),
    ]

    # Fixme
    # Pendiente logica para cargar documentos de modulos adicionales

    return DOCUMENTOS
