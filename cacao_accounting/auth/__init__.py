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
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask.typing import ResponseReturnValue
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.auth import helpers
from cacao_accounting.database import User, database
from cacao_accounting.document_flow.status import _
from cacao_accounting.limiter import limiter

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
    flash(_("Favor iniciar sesión para acceder al sistema."))
    return INICIO_SESION


def proteger_passwd(clave):
    """Devuelve una contraseña salteada con bcrypt."""
    clave_encriptada = ph.hash(clave.encode())
    return clave_encriptada.encode()


def validar_acceso(usuario, clave) -> bool:
    """Verifica el inicio de sesión del usuario."""
    return helpers.validar_acceso(usuario, clave)


def _session_security_is_active() -> bool:
    """Return True when origin protection is enabled and SMTP is ready."""
    from cacao_accounting.admin.session_security_service import (
        is_session_security_enabled,
        smtp_is_configured,
    )

    return is_session_security_enabled() and smtp_is_configured()


@login.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def inicio_sesion():  # pragma: no cover
    """Inicio de sesión del usuario."""
    from flask_login import current_user

    from cacao_accounting.auth.account_throttling import (
        esta_bloqueada,
        notificar_intento_fallido,
        registrar_intento_exitoso,
        registrar_intento_fallido,
        tiempo_restante_bloqueo,
    )
    from cacao_accounting.auth.forms import LoginForm

    form = LoginForm()
    if current_user.is_authenticated:
        return redirect("/app")

    if not form.validate_on_submit():
        return render_template("login.html", form=form, titulo=_("Inicio de Sesion - Cacao Accounting"))

    usuario_previo = helpers.obtener_usuario(form.usuario.data)
    if usuario_previo is not None and esta_bloqueada(usuario_previo):
        segundos = tiempo_restante_bloqueo(usuario_previo)
        minutos = (segundos or 0) // 60 + 1
        flash(_("Cuenta bloqueada temporalmente. Intente de nuevo en {} minuto(s).").format(minutos))
        return INICIO_SESION

    identidad = helpers.autenticar_usuario(form.usuario.data, form.acceso.data)
    if identidad is None:
        if usuario_previo is not None:
            registrar_intento_fallido(usuario_previo)
            notificar_intento_fallido(usuario_previo)
            database.session.commit()
        flash(_("Inicio de Sesion Incorrecto."))
        return INICIO_SESION

    registrar_intento_exitoso(identidad)
    database.session.commit()

    if not helpers.puede_iniciar_en_escritorio(identidad):
        flash(_("Solo un usuario administrador puede iniciar sesion."))
        return INICIO_SESION

    if _session_security_is_active():
        from cacao_accounting.auth.device_verification import usuario_tiene_email
        from cacao_accounting.admin.session_security_service import usuario_actual_ip

        device_token = request.cookies.get("__Secure-device-id") or request.cookies.get("device-id")
        from cacao_accounting.auth.device_verification import verificar_cookie_dispositivo

        if device_token and verificar_cookie_dispositivo(identidad.id, device_token):
            helpers.asignar_token_para_usuario(identidad)
            login_user(identidad)
            return helpers.redireccion_despues_de_login()

        if not usuario_tiene_email(identidad):
            flash(_("Su cuenta no tiene un correo electrónico configurado. Contacte al administrador."))
            return INICIO_SESION

        from cacao_accounting.auth.device_verification import enviar_otp_por_email, generar_otp

        otp_code = generar_otp(identidad.id, purpose="device_verification")
        session["otp_user_id"] = identidad.id
        session["otp_ip"] = usuario_actual_ip()
        session["otp_user_agent"] = (request.user_agent.string or "")[:255]
        enviar_otp_por_email(identidad, otp_code)
        database.session.commit()
        flash(_("Se envió un código de verificación a su correo electrónico."))
        return redirect(url_for("login.verify_otp"))

    helpers.asignar_token_para_usuario(identidad)
    login_user(identidad)
    return helpers.redireccion_despues_de_login()


@login.route("/auth/verify-otp", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def verify_otp():  # pragma: no cover
    """Verificación de OTP para dispositivos no reconocidos."""
    from cacao_accounting.auth.forms import OtpVerificationForm

    user_id = session.get("otp_user_id")
    if not user_id:
        flash(_("Sesión no válida. Inicie sesión nuevamente."))
        return INICIO_SESION

    user = database.session.get(User, user_id)
    if user is None or not user.active:
        session.pop("otp_user_id", None)
        flash(_("Sesión no válida. Inicie sesión nuevamente."))
        return INICIO_SESION

    form = OtpVerificationForm()
    if request.method == "POST" and form.validate_on_submit():
        from cacao_accounting.auth.device_verification import (
            establecer_cookie_dispositivo,
            validar_otp,
        )

        if validar_otp(user.id, form.code.data, purpose="device_verification"):
            token = establecer_cookie_dispositivo(
                user.id,
                user_agent=session.get("otp_user_agent"),
                ip_address=session.get("otp_ip"),
            )
            helpers.asignar_token_para_usuario(user)
            login_user(user)
            session.pop("otp_user_id", None)
            session.pop("otp_ip", None)
            session.pop("otp_user_agent", None)
            database.session.commit()

            response = redirect(helpers.redireccion_despues_de_login())
            cookie_name = "__Secure-device-id" if request.is_secure else "device-id"
            response.set_cookie(
                cookie_name,
                token,
                max_age=30 * 24 * 3600,
                httponly=True,
                secure=request.is_secure,
                samesite="Lax",
            )
            return response

        flash(_("Código de verificación incorrecto o expirado."))

    return render_template(
        "verify_otp.html",
        form=form,
        titulo=_("Verificación de Dispositivo"),
    )


@login.route("/auth/forgot-password", methods=["GET", "POST"])
@limiter.limit("3 per minute")
def forgot_password():  # pragma: no cover
    """Solicitud de recuperación de contraseña."""
    from cacao_accounting.auth.device_verification import (
        enviar_token_recuperacion_email,
        generar_token_recuperacion,
        usuario_tiene_email,
    )
    from cacao_accounting.auth.forms import ForgotPasswordForm

    form = ForgotPasswordForm()
    if request.method == "POST" and form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = database.session.execute(database.select(User).filter(User.e_mail.ilike(email))).scalar_one_or_none()

        if user and user.active and usuario_tiene_email(user):
            token = generar_token_recuperacion(user.id)
            enviar_token_recuperacion_email(user, token)
            database.session.commit()

        flash(_("Si el correo electrónico está registrado, recibirá un enlace de recuperación."))
        return redirect(url_for("login.forgot_password"))

    return render_template(
        "forgot_password.html",
        form=form,
        titulo=_("Recuperación de Contraseña"),
    )


@login.route("/auth/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def reset_password(token: str):  # pragma: no cover
    """Establecimiento de nueva contraseña con token de recuperación."""
    from cacao_accounting.auth import proteger_passwd as _proteger_passwd
    from cacao_accounting.auth.device_verification import validar_token_recuperacion
    from cacao_accounting.auth.forms import ResetPasswordForm
    from cacao_accounting.auth.helpers import validar_clave_segura

    user = validar_token_recuperacion(token)
    if user is None:
        flash(_("El enlace de recuperación no es válido o ha expirado."))
        return redirect(url_for("login.forgot_password"))

    form = ResetPasswordForm()
    if request.method == "POST" and form.validate_on_submit():
        if not validar_clave_segura(form.new_password.data):
            form.new_password.errors.append(
                _("Contraseña muy débil. Use al menos 8 caracteres, mayúsculas, minúsculas, números y símbolos.")
            )
            return render_template(
                "reset_password.html",
                form=form,
                token=token,
                titulo=_("Restablecer Contraseña"),
            )

        user.password = _proteger_passwd(form.new_password.data)
        database.session.commit()
        flash(_("Contraseña actualizada correctamente. Puede iniciar sesión."))
        return redirect(url_for("login.inicio_sesion"))

    return render_template(
        "reset_password.html",
        form=form,
        token=token,
        titulo=_("Restablecer Contraseña"),
    )


@login.route("/exit")
@login.route("/logout")
@login.route("/salir")
def cerrar_sesion():  # pragma: no cover
    """Finaliza la sesion actual."""
    if current_user and current_user.is_authenticated:
        current_user.token = None
    logout_user()
    session.clear()
    cookie_name = "__Secure-device-id" if request.is_secure else "device-id"
    resp = redirect("/login")
    resp.delete_cookie(cookie_name)
    return resp


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
        flash(_("El correo electrónico ya está en uso por otro usuario."))
        return _render_profile(profile_form, password_form)

    _apply_profile_form(profile_form, email)
    database.session.commit()
    flash(_("Información de perfil actualizada correctamente."))
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
    current_user.language = profile_form.language.data or None


def _handle_password_change(profile_form: Any, password_form: Any) -> ResponseReturnValue | None:
    """Change the current user's password when its form was submitted."""
    if not password_form.cambiar_clave.data:
        return None
    if not password_form.validate():
        _normalize_confirm_password_errors(password_form)
        return _render_profile(profile_form, password_form)
    if not _current_password_is_valid(password_form):
        password_form.current_password.errors.append(_("Contraseña actual incorrecta."))
        return _render_profile(profile_form, password_form)
    if not helpers.validar_clave_segura(password_form.new_password.data):
        password_form.new_password.errors.append(
            _("Contraseña muy débil. Use al menos 8 caracteres, mayúsculas, minúsculas, números y símbolos.")
        )
        return _render_profile(profile_form, password_form)

    current_user.password = proteger_passwd(password_form.new_password.data)
    database.session.commit()
    flash(_("Contraseña actualizada correctamente."))
    return redirect(url_for("login.profile"))


def _normalize_confirm_password_errors(password_form: Any) -> None:
    """Normalize password confirmation validation messages."""
    if password_form.confirm_password.errors:
        password_form.confirm_password.errors = [
            _("Las contraseñas no coinciden.") if err == "Las contraseñas deben coincidir" else err
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
