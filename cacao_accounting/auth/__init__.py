# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Inición de sesión de usuarios."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from argon2 import PasswordHasher
from flask import Blueprint, flash, redirect, render_template
from flask_login import LoginManager, login_required, login_user, logout_user

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.auth import helpers
from cacao_accounting.database import User, database
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
        QUERY = database.session.execute(database.select(User).filter_by(id=identidad)).first()
        try:
            return QUERY[0]
        except TypeError:
            return None
    else:
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
    return helpers.validar_acceso(usuario, clave)


@login.route("/login", methods=["GET", "POST"])
def inicio_sesion():  # pragma: no cover
    """Inicio de sesión del usuario."""
    from flask_login import current_user

    from cacao_accounting.auth.forms import LoginForm

    form = LoginForm()
    if current_user.is_authenticated:
        return redirect("/app")

    if not form.validate_on_submit():
        return render_template("login.html", form=form, titulo="Inicio de Sesion - Cacao Accounting")

    identidad = helpers.autenticar_usuario(form.usuario.data, form.acceso.data)
    if identidad is None:
        flash("Inicio de Sesion Incorrecto.")
        return INICIO_SESION

    if not helpers.puede_iniciar_en_escritorio(identidad):
        flash("Solo un usuario administrador puede iniciar sesion.")
        return INICIO_SESION

    helpers.asignar_token_para_usuario(identidad)
    login_user(identidad)
    return helpers.redireccion_despues_de_login()


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
