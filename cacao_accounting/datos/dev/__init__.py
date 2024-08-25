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

"""Datos de ejemplo."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# ---------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.auth.roles import asigna_rol_a_usuario
from cacao_accounting.database import database
from cacao_accounting.datos.dev.data import (
    BASE_USUARIOS,
    CENTROS_DE_COSTOS,
    CUENTAS,
    ENTIDADES,
    PERIODOS,
    PROYECTOS,
    SERIES,
    TASAS_DE_CAMBIO,
    UNIDADES,
    USUARIO_ROLES,
)
from cacao_accounting.logs import log


def asignar_usuario_a_roles():
    """Asigna roles a usuarios."""
    for r in USUARIO_ROLES:
        asigna_rol_a_usuario(r[0], r[1])


def demo_usuarios():
    """Usuarios para demostracion."""
    from cacao_accounting.database import Usuario

    for u in BASE_USUARIOS:
        usuario = Usuario(
            usuario=u.get("usuario"),
            correo_e=u.get("correo_e"),
            clave_acceso=u.get("clave_acceso"),
            creado_por="system",
        )
        database.session.add(usuario)
    database.session.commit()


def demo_entidad():
    """Entidad de demostración."""
    for e in ENTIDADES:
        database.session.add(e)
    database.session.commit()


def series_predeterminadas():
    """Crear series predeterminadas."""
    for s in SERIES:
        database.session.add(s)
    database.session.commit()


def demo_unidades():
    """Unidades de Negocio de Demostración."""
    for u in UNIDADES:
        database.session.add(u)
    database.session.commit()


def cargar_catalogo_de_cuentas():
    """Catalogo de cuentas de demostración."""
    from cacao_accounting.contabilidad.ctas import base, cargar_catalogos

    log.debug("Cargando catalogos de cuentas.")
    cargar_catalogos(base, "cacao")
    cargar_catalogos(base, "dulce")
    cargar_catalogos(base, "cafe")

    for c in CUENTAS:
        database.session.add(c)
    database.session.commit()


def cargar_centros_de_costos():
    """Centros de Costos de demostración."""
    for cc in CENTROS_DE_COSTOS:
        database.session.add(cc)
    database.session.commit()


def cargar_proyectos():
    """Proyectos de demostración."""
    for p in PROYECTOS:
        database.session.add(p)
    database.session.commit()


def tasas_de_cambio():
    """Tasa de Cambio de demostración."""
    for t in TASAS_DE_CAMBIO:
        database.session.add(t)
    database.session.commit()


def master_data():
    """Carga datos maestros de desarrollo a la base de datos."""
    log.warning("Iniciando carga de master data de pruebas.")

    demo_usuarios()
    asignar_usuario_a_roles()
    demo_entidad()
    demo_unidades()
    cargar_centros_de_costos()
    cargar_proyectos()
    tasas_de_cambio()
    cargar_catalogo_de_cuentas()

    log.debug("Master data de prueba creada correctamente.")


def periodo_contable():
    """Crea periodos contables para desarrollo."""
    for p in PERIODOS:
        database.session.add(p)
    database.session.commit()


def transacciones():
    """Crea transacciones de desarrollo en la base de datos."""
    periodo_contable()
    log.debug("Transacciones de Pruebas Creadas correctamente.")


def dev_data():
    """Carga datos de desarrollo a la base de datos."""
    log.trace("Iniciando carga de datos de prueba.")
    master_data()
    transacciones()
