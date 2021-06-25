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
Página principal de la aplicación.
"""


from flask import Blueprint, current_app, render_template
from flask_login import login_required

cacao_app = Blueprint("cacao_app", __name__, template_folder="templates")


@cacao_app.route("/app")
@login_required
def pagina_inicio():
    return render_template("app.html")


def bd_actual():
    """
    Devuelve el motor de base de datos según la cadena de conexión establecida
    en la configuración de la aplicación actual.
    """
    uri = str(current_app.config["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        db = "Sqlite"
    elif uri.startswith("postgresql"):
        db = "Postgresql"
    elif uri.startswith("mysql"):
        db = "MySQL"
    elif uri.startswith("mssql"):
        db = "MS SQL Server"
    elif uri.startswith("mariadb"):
        db = "Mariadb"
    else:
        db = None
    return db


def dev_info():
    from cacao_accounting.version import VERSION
    from cacao_accounting.database import DBVERSION

    info = {
        "app": {
            "version": VERSION,
            "dbversion": DBVERSION,
        }
    }
    return info


@cacao_app.route("/development")
@cacao_app.route("/info")
def informacion_para_desarrolladores():
    from os import environ

    if (current_app.config.get("ENV") == "development") or ("CACAO_TEST" in environ):
        return render_template("development.html", info=dev_info(), db=bd_actual(), current_app=current_app)
    else:
        from flask import redirect

        return redirect("/login")
