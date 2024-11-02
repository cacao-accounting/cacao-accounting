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


"""Página principal de la aplicación."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from os import environ

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Blueprint, current_app, render_template
from flask_login import login_required

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.version import VERSION

cacao_app = Blueprint("cacao_app", __name__, template_folder="templates")


@cacao_app.route("/")
@cacao_app.route("/app")
@cacao_app.route("/home")
@cacao_app.route("/index")
@login_required
def pagina_inicio():
    """Esta es la primer pagina mostrada al usuario luego de iniciar sesion."""
    return render_template("app.html")


def bd_actual():  # pragma: no cover
    """Devuelve el motor de base de datos."""
    uri = str(current_app.config.get("SQLALCHEMY_DATABASE_URI"))
    if uri.startswith("sqlite"):
        db_engine = "Sqlite"
    elif uri.startswith("postgresql"):
        db_engine = "Postgresql"
    elif uri.startswith("mysql"):
        db_engine = "MySQL"
    elif uri.startswith("mssql"):
        db_engine = "MS SQL Server"
    elif uri.startswith("mariadb"):
        db_engine = "Mariadb"
    else:
        db_engine = None
    return db_engine


def dev_info():
    """Funcion auxiliar para obtener información del sistema."""
    info = {
        "app": {
            "version": VERSION,
        }
    }
    return info


@cacao_app.route("/info")
@cacao_app.route("/dev")
@cacao_app.route("/development")
@login_required
def informacion_para_desarrolladores():
    """Pagina con información para desarrolladores o administradores del sistema."""
    import platform
    import sys
    from cacao_accounting.database.helpers import db_version

    return render_template(
        "development.html",
        info=dev_info(),
        db=bd_actual(),
        current_app=current_app,
        os=platform.system(),
        db_version=db_version(),
        test="CACAO_TEST" in environ,
        py_version=sys.version,
    )
