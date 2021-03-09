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
Definición de herramientas varias.
"""

from os import path

from cacao_accounting.database import db
from cacao_accounting.datos import base_data, demo_data
from cacao_accounting.metadata import DEVELOPMENT


home = path.abspath(path.dirname(__file__))
plantillas = path.join(home, "templates")
archivos = path.join(home, "static")


def db_metadata():
    """
    Actualiza metadatos en la base de datos.
    """
    from cacao_accounting.database import DBVERSION, Metadata
    from cacao_accounting.version import VERSION

    meta = Metadata(
        cacaoversion=VERSION,
        dbversion=DBVERSION,
    )
    db.session.add(meta)
    db.session.commit()


def verifica_db_version(app):
    """
    Utilidad para validar si se requeire actualizar la base de datos.
    """
    from cacao_accounting.database import Metadata, DBVERSION
    from cacao_accounting.loggin import log
    from cacao_accounting.version import VERSION

    with app.app_context():
        meta = Metadata.query.all()

        migrardb = False
        while migrardb == False:  # noqa: E712
            for i in meta:
                if (i.dbversion == DBVERSION) and (i.cacaoversion == VERSION):
                    pass
                else:
                    log.info("Se requiere actualizar esquema de base de datos.")
                    migrardb = True
            break

    return migrardb


def inicia_base_de_datos(app):
    """Crea el esquema de la base de datos."""

    with app.app_context():
        db.create_all()
        if DEVELOPMENT:

            base_data(carga_rapida=True)
            demo_data()
        else:
            base_data(carga_rapida=False)
        db_metadata()


def verifica_acceso_db(app):
    """
    Utileria para verificar si el acceso a la base de datos funciona.
    """
    from cacao_accounting.database import Metadata
    from cacao_accounting.loggin import log

    log.info("Verificando acceso a la base de datos.")
    with app.app_context():
        try:
            meta = Metadata.query.all()
            for i in meta:
                pass
            log.info("Acceso a la base de datos exitoso.")
            db = True
        except:  # noqa: E722
            db = False
    return db
