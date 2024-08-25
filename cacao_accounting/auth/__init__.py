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

"""Inición de sesión de usuarios."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from argon2 import PasswordHasher
from flask import Blueprint, current_app, flash, redirect, render_template
from flask_login import LoginManager, login_required, login_user, logout_user
from jwt import encode

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.database import Usuario
from cacao_accounting.logs import log


# <---------------------------------------------------------------------------------------------> #
# Logica de inicio de sesión.
# <---------------------------------------------------------------------------------------------> #
login = Blueprint("login", __name__, template_folder="templates")
administrador_sesion = LoginManager()
ph = PasswordHasher()

INICIO_SESION = redirect("/login")


@administrador_sesion.user_loader
def cargar_sesion(identidad):  # pragma: no cover
    """Devuelve la entrada correspondiente al usuario que inicio sesión."""
    if identidad is not None:
        return Usuario.query.get(identidad)
    return None


@administrador_sesion.unauthorized_handler
def no_autorizado():  # pragma: no cover
    """Redirecciona al inicio de sesión usuarios no autorizados."""
    flash("Favor iniciar sesión para acceder al sistema.")
    return INICIO_SESION


def proteger_passwd(clave):
    """Devuelve una contraseña salteada con bcrytp."""

    clave_encriptada = ph.hash(clave.encode())
    return clave_encriptada.encode()


def validar_acceso(usuario, clave) -> bool:
    """Verifica el inicio de sesión del usuario."""
    from argon2.exceptions import VerifyMismatchError

    acceso = clave
    registro = Usuario.query.filter_by(usuario=usuario).first()

    if registro:

        try:
            ph.verify(registro.clave_acceso, acceso)
            return True

        except VerifyMismatchError:
            return False

    else:
        return False


@login.route("/login", methods=["GET", "POST"])
def inicio_sesion():  # pragma: no cover
    """Inicio de sesión del usuario."""
    from flask_login import current_user

    from cacao_accounting.auth.forms import LoginForm

    form = LoginForm()
    if current_user.is_authenticated:
        return redirect("/app")
    else:
        if form.validate_on_submit():
            if validar_acceso(form.usuario.data, form.acceso.data):
                identidad = Usuario.query.filter_by(usuario=form.usuario.data).first()

                # Api rest auth token.
                try:
                    # token should expire after 24 hrs
                    identidad.token = encode({"user_id": identidad.id}, current_app.config["SECRET_KEY"], algorithm="HS256")
                    assert identidad.token is not None  # nosec

                except Exception as e:
                    assert e is not None  # nosec
                    log.warning("No se pudo generar auth token.")

                login_user(identidad)
                return redirect("/app")
            else:
                flash("Inicio de Sesion Incorrecto.")
                return INICIO_SESION
        return render_template("login.html", form=form, titulo="Inicio de Sesion - Cacao Accounting")


@login.route("/exit")
@login.route("/logout")
@login.route("/salir")
def cerrar_sesion():  # pragma: no cover
    """Finaliza la sesion actual."""
    logout_user()
    return INICIO_SESION


@login.route("/permisos_usuario")
@login_required
def test_roles():  # pragma: no cover
    """Verifica los permisos del usuario actual."""
    from flask_login import current_user

    from cacao_accounting.auth.permisos import Permisos
    from cacao_accounting.auth.roles import obtener_roles_por_usuario
    from cacao_accounting.database import Modulos

    MODULOS = Modulos.query.all()

    return render_template(
        "test_roles.html",
        permisos=Permisos,
        roles=obtener_roles_por_usuario(current_user.usuario),
        modulos=MODULOS,
    )
