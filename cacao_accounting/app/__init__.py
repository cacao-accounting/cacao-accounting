# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes


"""Página principal de la aplicación."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from os import environ

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Blueprint, current_app, jsonify, render_template
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
    match uri:
        case _ if uri.startswith("sqlite"):
            return "Sqlite"
        case _ if uri.startswith("postgresql"):
            return "Postgresql"
        case _ if uri.startswith("mysql"):
            return "MySQL"
        case _ if uri.startswith("mssql"):
            return "MS SQL Server"
        case _ if uri.startswith("mariadb"):
            return "Mariadb"
        case _:
            return None


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


@cacao_app.route("/ping")
@cacao_app.route("/check")
def ping():
    """Valida que la app se esta ejecutando."""

    resp = jsonify(success=True)
    resp.status_code = 200

    return resp
