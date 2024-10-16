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

"""Datos básicos para iniciar el sistema."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from os import environ

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import current_app

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.logs import log
from cacao_accounting.modulos import init_modulos


def registra_monedas(carga_rapida):
    """Carga de monedas al sistema."""
    from teritorio import Currencies

    from cacao_accounting.database import Currency, database

    log.trace("Iniciando carga de base monedas a la base de datos.")

    if carga_rapida:
        MONEDAS = (
            Currency(code="NIO", name="Cordobas", decimals=2),
            Currency(
                code="USD",
                name="Dolares",
                decimals=2,
            ),
        )
        for m in MONEDAS:
            database.session.add(m)
            database.session.commit()
    else:
        for currency in Currencies():
            database.session.add(
                Currency(
                    code=currency.code,
                    name=currency.name,
                    decimals=currency.minor_units,
                )
            )
            database.session.commit()
    log.debug("Monedas cargadas Correctamente")


def crea_usuario_admin(user: str, passwd: str):
    """
    Crea el usuario administrador.

    Si no se encuentra definido a nivel de variables de entorno se crea utilizando valores
    predeterminados, no se recomienda utilizar los valores predeterminados si la instancia va
    a estar expuesta de forma publica a la internet.
    """
    from flask import current_app

    from cacao_accounting.auth import proteger_passwd
    from cacao_accounting.database import User, database

    log.info("Creando Usuario Administrador")

    with current_app.app_context():
        usuario = User(user=user, password=proteger_passwd(passwd))
        database.session.add(usuario)
        database.session.commit()
        asigna_rol_a_usuario(usuario=user, rol="admin")
        log.trace("Usuario administrador creado correctamente.")


def base_data(user, passwd, carga_rapida):
    """Definición de metodo para cargar información base al sistema."""
    if environ.get("CACAO_PRINT_DATABASE_URI") and environ.get("CACAO_TEST"):
        with current_app.app_context():
            from cacao_accounting.database import database
            from sqlalchemy.sql import text

            DABATASE_URI = current_app.config.get("SQLALCHEMY_DATABASE_URI")
            log.warning(DABATASE_URI)

            if DABATASE_URI.startswith("mysql+pymysql"):
                log.info("Running on MySQL.")
                Q = database.session.execute(text("SELECT version();"))
                for i in Q:
                    log.info("Versión de base de datos" + str(i))
            elif DABATASE_URI.startswith("postgresql+pg8000") or DABATASE_URI.startswith("postgresql+psycopg2"):
                log.info("Running on Postgresql.")
                Q = database.session.execute(text("SELECT VERSION();"))
                for i in Q:
                    log.info("Versión de base de datos" + str(i))
            else:
                log.info("Running on SQLITE.")
                Q = database.session.execute(text("select sqlite_version();"))
                for i in Q:
                    log.info("Versión de base de datos" + str(i))

    log.debug("Iniciando carga de datos base al sistema.")
    init_modulos()
    crea_roles_predeterminados()
    cargar_permisos_predeterminados()
    crea_usuario_admin(user, passwd)
    registra_monedas(carga_rapida=carga_rapida)
    log.debug("Batos base cargados en la base de datos.")
