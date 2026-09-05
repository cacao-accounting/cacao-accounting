# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios del modulo de administración de sesión."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# --------------------------------------------------------------------------------------
from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, SelectMultipleField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional
from wtforms.widgets import CheckboxInput, ListWidget


class LoginForm(FlaskForm):
    """Formulario de inicio de sesión."""

    usuario = StringField(validators=[DataRequired()])
    acceso = PasswordField(validators=[DataRequired()])
    inicio_sesion = SubmitField()


class ProfileForm(FlaskForm):
    """Formulario para actualizar información personal."""

    name = StringField(lazy_gettext("Nombre"), validators=[Optional()])
    name2 = StringField(lazy_gettext("Segundo nombre"), validators=[Optional()])
    last_name = StringField(lazy_gettext("Apellido"), validators=[Optional()])
    last_name2 = StringField(lazy_gettext("Segundo apellido"), validators=[Optional()])
    e_mail = StringField(lazy_gettext("Correo electrónico"), validators=[Optional(), Email()])
    phone = StringField(lazy_gettext("Teléfono"), validators=[Optional()])
    language = SelectField(
        lazy_gettext("Idioma"),
        choices=[
            ("", lazy_gettext("Predeterminado del sistema")),
            ("es", lazy_gettext("Español")),
            ("en", "English"),
        ],
        validators=[Optional()],
    )
    guardar_perfil = SubmitField(lazy_gettext("Guardar cambios"))


class PasswordChangeForm(FlaskForm):
    """Formulario para cambiar la contraseña del usuario."""

    current_password = PasswordField(lazy_gettext("Contraseña actual"), validators=[DataRequired()])
    new_password = PasswordField(lazy_gettext("Nueva contraseña"), validators=[DataRequired()])
    confirm_password = PasswordField(
        lazy_gettext("Confirmar contraseña"),
        validators=[DataRequired(), EqualTo("new_password", message=lazy_gettext("Las contraseñas deben coincidir"))],
    )
    cambiar_clave = SubmitField(lazy_gettext("Cambiar contraseña"))


class UserCreateForm(FlaskForm):
    """Formulario para crear usuarios."""

    usuario = StringField(lazy_gettext("Usuario"), validators=[DataRequired(), Length(min=3, max=15)])
    name = StringField(lazy_gettext("Nombre"), validators=[Optional()])
    name2 = StringField(lazy_gettext("Segundo nombre"), validators=[Optional()])
    last_name = StringField(lazy_gettext("Apellido"), validators=[Optional()])
    last_name2 = StringField(lazy_gettext("Segundo apellido"), validators=[Optional()])
    e_mail = StringField(lazy_gettext("Correo electrónico"), validators=[Optional(), Email()])
    phone = StringField(lazy_gettext("Teléfono"), validators=[Optional()])
    classification = SelectField(
        lazy_gettext("Clasificación"),
        choices=[
            ("system", lazy_gettext("Sistema (System)")),
            ("customer", lazy_gettext("Cliente (Customer)")),
            ("supplier", lazy_gettext("Proveedor (Supplier)")),
        ],
        validators=[DataRequired()],
        default="system",
    )
    party_id = SelectField(lazy_gettext("Tercero del portal"), choices=[], validators=[Optional()])
    company = SelectField(lazy_gettext("Compañía del portal"), choices=[], validators=[Optional()])
    active = BooleanField(lazy_gettext("Habilitado"), default=True)
    password = PasswordField(lazy_gettext("Contraseña"), validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        lazy_gettext("Confirmar contraseña"),
        validators=[DataRequired(), EqualTo("password", message=lazy_gettext("Las contraseñas deben coincidir"))],
    )
    crear_usuario = SubmitField(lazy_gettext("Crear usuario"))


class UserEditForm(FlaskForm):
    """Formulario para editar usuarios."""

    usuario = StringField(lazy_gettext("Usuario"), validators=[DataRequired(), Length(min=3, max=15)])
    name = StringField(lazy_gettext("Nombre"), validators=[Optional()])
    name2 = StringField(lazy_gettext("Segundo nombre"), validators=[Optional()])
    last_name = StringField(lazy_gettext("Apellido"), validators=[Optional()])
    last_name2 = StringField(lazy_gettext("Segundo apellido"), validators=[Optional()])
    e_mail = StringField(lazy_gettext("Correo electrónico"), validators=[Optional(), Email()])
    phone = StringField(lazy_gettext("Teléfono"), validators=[Optional()])
    classification = SelectField(
        lazy_gettext("Clasificación"),
        choices=[
            ("system", lazy_gettext("Sistema (System)")),
            ("customer", lazy_gettext("Cliente (Customer)")),
            ("supplier", lazy_gettext("Proveedor (Supplier)")),
            ("admin", lazy_gettext("Administrador (Admin)")),
        ],
        validators=[DataRequired()],
        default="system",
    )
    party_id = SelectField(lazy_gettext("Tercero del portal"), choices=[], validators=[Optional()])
    company = SelectField(lazy_gettext("Compañía del portal"), choices=[], validators=[Optional()])
    active = BooleanField(lazy_gettext("Habilitado"))
    guardar_usuario = SubmitField(lazy_gettext("Guardar usuario"))


class UserPasswordForm(FlaskForm):
    """Formulario para cambiar contraseña de usuario desde administración."""

    password = PasswordField(lazy_gettext("Nueva contraseña"), validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        lazy_gettext("Confirmar contraseña"),
        validators=[DataRequired(), EqualTo("password", message=lazy_gettext("Las contraseñas deben coincidir"))],
    )
    cambiar_clave = SubmitField(lazy_gettext("Cambiar contraseña"))


class MultiCheckboxField(SelectMultipleField):
    """Campo para representar una lista de opciones con checkboxes."""

    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class UserRoleForm(FlaskForm):
    """Formulario para asignar roles a un usuario."""

    roles = MultiCheckboxField(lazy_gettext("Roles"), validators=[Optional()], choices=[])
    guardar_roles = SubmitField(lazy_gettext("Guardar roles"))


class UserCompanyAccessForm(FlaskForm):
    """Formulario para asignar compañías a un usuario interno."""

    companies = MultiCheckboxField(lazy_gettext("Compañías"), validators=[Optional()], choices=[])
    guardar_companias = SubmitField(lazy_gettext("Guardar compañías"))


class RoleForm(FlaskForm):
    """Formulario para crear o editar un rol."""

    name = StringField(lazy_gettext("Nombre del rol"), validators=[DataRequired(), Length(min=3, max=50)])
    note = StringField(lazy_gettext("Detalle"), validators=[Optional(), Length(max=100)])
    guardar_rol = SubmitField(lazy_gettext("Guardar rol"))


class OtpVerificationForm(FlaskForm):
    """Formulario para verificar un código OTP de 6 dígitos."""

    code = StringField(lazy_gettext("Código de verificación"), validators=[DataRequired(), Length(min=6, max=6)])
    verificar = SubmitField(lazy_gettext("Verificar"))


class ForgotPasswordForm(FlaskForm):
    """Formulario para solicitar recuperación de contraseña."""

    email = StringField(lazy_gettext("Correo electrónico"), validators=[DataRequired(), Email()])
    enviar = SubmitField(lazy_gettext("Enviar enlace de recuperación"))


class ResetPasswordForm(FlaskForm):
    """Formulario para restablecer contraseña con token de recuperación."""

    new_password = PasswordField(lazy_gettext("Nueva contraseña"), validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        lazy_gettext("Confirmar contraseña"),
        validators=[DataRequired(), EqualTo("new_password", message=lazy_gettext("Las contraseñas deben coincidir"))],
    )
    restablecer = SubmitField(lazy_gettext("Restablecer contraseña"))
