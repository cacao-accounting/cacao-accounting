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

    log.debug("Creando usuarios de prueba.")
    usuarios = [
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


ENTIDAD_DEMO1 = {
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
    "habilitada": True,
    "predeterminada": True,
    "status": "predeterminada",
}


ENTIDAD_DEMO2 = {
    "id": "cafe",
    "razon_social": "Mundo Cafe Sociedad Anonima",
    "nombre_comercial": "Mundo Cafe",
    "id_fiscal": "J0310000000001",
    "moneda": "USD",
    "tipo_entidad": "Sociedad",
    "correo_electronico": "info@mundocafe.com",
    "web": "mundocafe.com",
    "telefono1": "+505 8456 6542",
    "telefono2": "+505 8456 7542",
    "fax": "+505 8456 7546",
    "habilitada": True,
    "predeterminada": False,
    "status": "activa",
}

ENTIDAD_DEMO3 = {
    "id": "dulce",
    "razon_social": "Mundo Sabor Sociedad Anonima",
    "nombre_comercial": "Dulce Sabor",
    "id_fiscal": "J0310000000002",
    "moneda": "NIO",
    "tipo_entidad": "Sociedad",
    "correo_electronico": "info@chocoworld.com",
    "web": "chocoworld.com",
    "telefono1": "+505 8456 6543",
    "telefono2": "+505 8456 7543",
    "fax": "+505 8456 7545",
    "habilitada": False,
    "predeterminada": False,
    "status": "inactiva",
}


def _demo_entidad():
    """Entidad de demostración"""
    from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad

    log.debug("Creando entidades de prueba.")
    instancia_entidad = RegistroEntidad()
    instancia_entidad.crear_entidad(datos=ENTIDAD_DEMO1)
    instancia_entidad.crear_entidad(datos=ENTIDAD_DEMO2)
    instancia_entidad.crear_entidad(datos=ENTIDAD_DEMO3)


def _demo_unidades():
    """Unidades de Negocio de Demostración"""
    from cacao_accounting.database import Unidad

    log.debug("Cargando unidades de negocio de prueba.")
    unidades = [
        Unidad(
            nombre="Casa Matriz",
            entidad="cacao",
            id="matriz",
            status="activa",
        ),
        Unidad(
            nombre="Movil",
            entidad="cacao",
            id="movil",
            status="activa",
        ),
        Unidad(
            nombre="Masaya",
            entidad="cacao",
            id="masaya",
            status="inactiva",
        ),
    ]
    for unidad in unidades:
        db.session.add(unidad)
    db.session.commit()


def _catalogo():
    from cacao_accounting.contabilidad.ctas import base, desarrollo, cargar_catalogos

    log.debug("Cargando catalogos de cuentas.")
    cargar_catalogos(desarrollo, "cacao")
    cargar_catalogos(base, "dulce")
    cargar_catalogos(base, "cafe")


def demo_data():
    log.debug("Iniciando carga de entidades de prueba.")
    _demo_usuarios()
    _demo_entidad()
    _demo_unidades()
    _catalogo()
    log.debug("Entidades de pruebas creada correctamente.")
