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
Datos de ejemplo.
"""
from cacao_accounting.database import db
from cacao_accounting.loggin import log
# pylint: disable=import-outside-toplevel


def _demo_usuarios():
    """Usuarios para demostracion"""
    from cacao_accounting.database import Usuario
    from cacao_accounting.auth import proteger_passwd

    usuarios = [
        Usuario(
            id="cacao",
            correo_e="cacao@cacao_accounting.io",
            clave_acceso=proteger_passwd("cacao"),
        ),
        Usuario(
            id="admin",
            correo_e="admin@cacao_accounting.io",
            clave_acceso=proteger_passwd("admin"),
        ),
        Usuario(
            id="ventas",
            correo_e="ventas@cacao_accounting.io",
            clave_acceso=proteger_passwd("ventas"),
        ),
        Usuario(
            id="compras",
            correo_e="compras@cacao_accounting.io",
            clave_acceso=proteger_passwd("compras"),
        ),
        Usuario(
            id="conta",
            correo_e="contabilidad@cacao_accounting.io",
            clave_acceso=proteger_passwd("conta"),
        ),
        Usuario(
            id="almacen",
            correo_e="almacen@cacao_accounting.io",
            clave_acceso=proteger_passwd("almacen"),
        ),
        Usuario(
            id="caja",
            correo_e="caja@cacao_accounting.io",
            clave_acceso=proteger_passwd("caja"),
        ),
    ]
    for usuario in usuarios:
        db.session.add(usuario)
    db.session.commit()


def _demo_entidad():
    """Entidad de demostración"""
    from cacao_accounting.database import Entidad
    from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad

    demo = {
        "id": "cacao",
        "razon_social": "Choco Sonrisas Sociedad Anonima",
        "nombre_comercial": "Choco Sonrisas",
        "id_fiscal": "J0310000000000",
        "moneda": "NIO",
        "tipo_entidad": "Sociedad",
        "correo_electronico": "info@chocoworld.com",
        "web": "chocoworld.com",
        "telefono1": "+505 8456 6543",
        "telefono2": "+505 8456 7543",
        "fax": "+505 8456 7545",
        "pais": "Nicaragua",
        "departamento": "Managua",
        "ciudad": "Managua",
        "direccion1": "Edicio x",
        "direccion2": "Oficina 23",
        "calle": 25,
        "casa": 3,
        "habilitada": True,
        "predeterminada": True,
    }
    entidad = Entidad(**demo)
    RegistroEntidad.crear(entidad)


def _demo_unidades():
    """Unidades de Negocio de Demostración"""
    from cacao_accounting.database import Unidad

    unidades = [
        Unidad(
            nombre="Casa Matriz",
            entidad="cacao",
            id="matriz",
        ),
        Unidad(
            nombre="Movil",
            entidad="cacao",
            id="movil",
        ),
        Unidad(
            nombre="Masaya",
            entidad="cacao",
            id="masaya",
        ),
    ]
    for unidad in unidades:
        db.session.add(unidad)
    db.session.commit()


def _catalogo():
    from cacao_accounting.contabilidad.ctas import catalogo_base, cargar_catalogos

    cargar_catalogos(catalogo_base, "cacao")


def demo_data():
    log.debug("Iniciando carda de empresa de prueba.")
    _demo_usuarios()
    _demo_entidad()
    _demo_unidades()
    _catalogo()
    log.debug("Empresa de pruebas creada correctamente.")
