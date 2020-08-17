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


def _demo_usuarios():
    """Usuarios para demostracion"""
    from cacao_accounting.database import Usuario
    from cacao_accounting.auth import proteger_passwd

    usuarios = [
        Usuario(id="cacao", correo_e="cacao@cacao_accounting.io", clave_acceso=proteger_passwd("cacao"),),
        Usuario(id="admin", correo_e="admin@cacao_accounting.io", clave_acceso=proteger_passwd("admin"),),
        Usuario(id="ventas", correo_e="ventas@cacao_accounting.io", clave_acceso=proteger_passwd("ventas"),),
        Usuario(id="compras", correo_e="compras@cacao_accounting.io", clave_acceso=proteger_passwd("compras"),),
        Usuario(id="conta", correo_e="contabilidad@cacao_accounting.io", clave_acceso=proteger_passwd("conta"),),
        Usuario(id="almacen", correo_e="almacen@cacao_accounting.io", clave_acceso=proteger_passwd("almacen"),),
        Usuario(id="caja", correo_e="caja@cacao_accounting.io", clave_acceso=proteger_passwd("caja"),),
    ]
    for usuario in usuarios:
        db.session.add(usuario)
    db.session.commit()


def _demo_entidad():
    """Entidad de demostración"""
    from cacao_accounting.database import Entidad

    demo = Entidad(
        id="cacao", razon_social="Hot Chocolate CIA LTDA", nombre_comercial="Choco Sonrisas", id_fiscal="J310000001234"
    )
    db.session.add(demo)
    db.session.commit()


def _demo_unidades():
    """Unidades de Negocio de Demostración"""
    from cacao_accounting.database import Unidad

    unidades = [
        Unidad(nombre="Casa Matriz", entidad="cacao", id="matriz",),
        Unidad(nombre="Movil", entidad="cacao", id="movil",),
        Unidad(nombre="Masaya", entidad="cacao", id="masaya",),
    ]
    for unidad in unidades:
        db.session.add(unidad)
    db.session.commit()


def _catalogo():
    from cacao_accounting.contabilidad.ctas import catalogo_base, cargar_catalogos

    cargar_catalogos(catalogo_base, "cacao")


def demo_data():
    _demo_usuarios()
    _demo_entidad()
    _demo_unidades()
    _catalogo()
