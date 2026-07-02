# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Inicio de sesión de usuarios."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from typing import Any

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from argon2 import PasswordHasher
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.auth import helpers
from cacao_accounting.database import User, database

# <---------------------------------------------------------------------------------------------> #
# Logica de inicio de sesión.
# <---------------------------------------------------------------------------------------------> #
login = Blueprint("login", __name__, template_folder="templates")
administrador_sesion = LoginManager()
ph = PasswordHasher()

INICIO_SESION = redirect("/login")

PROFILE_HTML = "profile.html"
PROFILE_TITLE = "Mi Perfil - Cacao Accounting"


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
    """Devuelve una contraseña salteada con bcrypt."""
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
    from cacao_accounting.auth.permisos import Permisos
    from cacao_accounting.auth.roles import obtener_roles_por_usuario
    from cacao_accounting.database import Modulos

    MODULOS = Modulos.query.all()

    return render_template(
        "test_roles.html",
        permisos=Permisos,
        roles=obtener_roles_por_usuario(current_user.user),
        modulos=MODULOS,
    )


@login.route("/auth/profile", methods=["GET", "POST"])
@login_required
def profile():  # pragma: no cover
    """Muestra y actualiza el perfil del usuario."""
    from cacao_accounting.auth.forms import PasswordChangeForm, ProfileForm

    profile_form = ProfileForm(obj=current_user)
    password_form = PasswordChangeForm()

    if request.method == "POST":
        response = _handle_profile_post(profile_form, password_form)
        if response is not None:
            return response

    return _render_profile(profile_form, password_form)


def _handle_profile_post(profile_form: Any, password_form: Any) -> ResponseReturnValue | None:
    """Dispatch a profile POST request to the submitted action."""
    profile_response = _handle_profile_update(profile_form, password_form)
    if profile_response is not None:
        return profile_response
    return _handle_password_change(profile_form, password_form)


def _handle_profile_update(profile_form: Any, password_form: Any) -> ResponseReturnValue | None:
    """Persist personal profile information when its form was submitted."""
    if not profile_form.guardar_perfil.data or not profile_form.validate():
        return None

    email = profile_form.e_mail.data or None
    if email and _profile_email_exists_for_another_user(email):
        flash("El correo electrónico ya está en uso por otro usuario.")
        return _render_profile(profile_form, password_form)

    _apply_profile_form(profile_form, email)
    database.session.commit()
    flash("Información de perfil actualizada correctamente.")
    return redirect(url_for("login.profile"))


def _profile_email_exists_for_another_user(email: str) -> bool:
    """Return whether another user already owns the email address."""
    existing_user = database.session.execute(
        database.select(User).filter(User.e_mail == email, User.id != current_user.id)
    ).first()
    return existing_user is not None


def _apply_profile_form(profile_form: Any, email: str | None) -> None:
    """Copy validated profile form values into the current user."""
    current_user.name = profile_form.name.data
    current_user.name2 = profile_form.name2.data
    current_user.last_name = profile_form.last_name.data
    current_user.last_name2 = profile_form.last_name2.data
    current_user.e_mail = email
    current_user.phone = profile_form.phone.data


def _handle_password_change(profile_form: Any, password_form: Any) -> ResponseReturnValue | None:
    """Change the current user's password when its form was submitted."""
    if not password_form.cambiar_clave.data:
        return None
    if not password_form.validate():
        _normalize_confirm_password_errors(password_form)
        return _render_profile(profile_form, password_form)
    if not _current_password_is_valid(password_form):
        password_form.current_password.errors.append("Contraseña actual incorrecta.")
        return _render_profile(profile_form, password_form)
    if not helpers.validar_clave_segura(password_form.new_password.data):
        password_form.new_password.errors.append(
            "Contraseña muy débil. Use al menos 8 caracteres, mayúsculas, minúsculas, números y símbolos."
        )
        return _render_profile(profile_form, password_form)

    current_user.password = proteger_passwd(password_form.new_password.data)
    database.session.commit()
    flash("Contraseña actualizada correctamente.")
    return redirect(url_for("login.profile"))


def _normalize_confirm_password_errors(password_form: Any) -> None:
    """Normalize password confirmation validation messages."""
    if password_form.confirm_password.errors:
        password_form.confirm_password.errors = [
            "Las contraseñas no coinciden." if err == "Las contraseñas deben coincidir" else err
            for err in password_form.confirm_password.errors
        ]


def _current_password_is_valid(password_form: Any) -> bool:
    """Return whether the submitted current password authenticates the user."""
    return helpers.autenticar_usuario(current_user.user, password_form.current_password.data) is not None


def _render_profile(profile_form: Any, password_form: Any) -> str:
    """Render the profile template with both forms."""
    return render_template(
        PROFILE_HTML,
        profile_form=profile_form,
        password_form=password_form,
        titulo=PROFILE_TITLE,
    )
