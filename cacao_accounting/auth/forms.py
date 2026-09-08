# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios del modulo de administración de sesión."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# --------------------------------------------------------------------------------------
from cacao_accounting.i18n import _l
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

    name = StringField(_l("Nombre"), validators=[Optional()])
    name2 = StringField(_l("Segundo nombre"), validators=[Optional()])
    last_name = StringField(_l("Apellido"), validators=[Optional()])
    last_name2 = StringField(_l("Segundo apellido"), validators=[Optional()])
    e_mail = StringField(_l("Correo electrónico"), validators=[Optional(), Email()])
    phone = StringField(_l("Teléfono"), validators=[Optional()])
    language = SelectField(
        _l("Idioma"),
        choices=[
            ("", _l("Predeterminado del sistema")),
            ("es", _l("Español")),
            ("en", "English"),
        ],
        validators=[Optional()],
    )
    guardar_perfil = SubmitField(_l("Guardar cambios"))


class PasswordChangeForm(FlaskForm):
    """Formulario para cambiar la contraseña del usuario."""

    current_password = PasswordField(_l("Contraseña actual"), validators=[DataRequired()])
    new_password = PasswordField(_l("Nueva contraseña"), validators=[DataRequired()])
    confirm_password = PasswordField(
        _l("Confirmar contraseña"),
        validators=[DataRequired(), EqualTo("new_password", message=_l("Las contraseñas deben coincidir"))],
    )
    cambiar_clave = SubmitField(_l("Cambiar contraseña"))


class UserCreateForm(FlaskForm):
    """Formulario para crear usuarios."""

    usuario = StringField(_l("Usuario"), validators=[DataRequired(), Length(min=3, max=15)])
    name = StringField(_l("Nombre"), validators=[Optional()])
    name2 = StringField(_l("Segundo nombre"), validators=[Optional()])
    last_name = StringField(_l("Apellido"), validators=[Optional()])
    last_name2 = StringField(_l("Segundo apellido"), validators=[Optional()])
    e_mail = StringField(_l("Correo electrónico"), validators=[Optional(), Email()])
    phone = StringField(_l("Teléfono"), validators=[Optional()])
    classification = SelectField(
        _l("Clasificación"),
        choices=[
            ("system", _l("Sistema (System)")),
            ("customer", _l("Cliente (Customer)")),
            ("supplier", _l("Proveedor (Supplier)")),
        ],
        validators=[DataRequired()],
        default="system",
    )
    party_id = SelectField(_l("Tercero del portal"), choices=[], validators=[Optional()])
    company = SelectField(_l("Compañía del portal"), choices=[], validators=[Optional()])
    active = BooleanField(_l("Habilitado"), default=True)
    password = PasswordField(_l("Contraseña"), validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        _l("Confirmar contraseña"),
        validators=[DataRequired(), EqualTo("password", message=_l("Las contraseñas deben coincidir"))],
    )
    crear_usuario = SubmitField(_l("Crear usuario"))


class UserEditForm(FlaskForm):
    """Formulario para editar usuarios."""

    usuario = StringField(_l("Usuario"), validators=[DataRequired(), Length(min=3, max=15)])
    name = StringField(_l("Nombre"), validators=[Optional()])
    name2 = StringField(_l("Segundo nombre"), validators=[Optional()])
    last_name = StringField(_l("Apellido"), validators=[Optional()])
    last_name2 = StringField(_l("Segundo apellido"), validators=[Optional()])
    e_mail = StringField(_l("Correo electrónico"), validators=[Optional(), Email()])
    phone = StringField(_l("Teléfono"), validators=[Optional()])
    classification = SelectField(
        _l("Clasificación"),
        choices=[
            ("system", _l("Sistema (System)")),
            ("customer", _l("Cliente (Customer)")),
            ("supplier", _l("Proveedor (Supplier)")),
            ("admin", _l("Administrador (Admin)")),
        ],
        validators=[DataRequired()],
        default="system",
    )
    party_id = SelectField(_l("Tercero del portal"), choices=[], validators=[Optional()])
    company = SelectField(_l("Compañía del portal"), choices=[], validators=[Optional()])
    active = BooleanField(_l("Habilitado"))
    guardar_usuario = SubmitField(_l("Guardar usuario"))


class UserPasswordForm(FlaskForm):
    """Formulario para cambiar contraseña de usuario desde administración."""

    password = PasswordField(_l("Nueva contraseña"), validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        _l("Confirmar contraseña"),
        validators=[DataRequired(), EqualTo("password", message=_l("Las contraseñas deben coincidir"))],
    )
    cambiar_clave = SubmitField(_l("Cambiar contraseña"))


class MultiCheckboxField(SelectMultipleField):
    """Campo para representar una lista de opciones con checkboxes."""

    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class UserRoleForm(FlaskForm):
    """Formulario para asignar roles a un usuario."""

    roles = MultiCheckboxField(_l("Roles"), validators=[Optional()], choices=[])
    guardar_roles = SubmitField(_l("Guardar roles"))


class UserCompanyAccessForm(FlaskForm):
    """Formulario para asignar compañías a un usuario interno."""

    companies = MultiCheckboxField(_l("Compañías"), validators=[Optional()], choices=[])
    guardar_companias = SubmitField(_l("Guardar compañías"))


class RoleForm(FlaskForm):
    """Formulario para crear o editar un rol."""

    name = StringField(_l("Nombre del rol"), validators=[DataRequired(), Length(min=3, max=50)])
    note = StringField(_l("Detalle"), validators=[Optional(), Length(max=100)])
    guardar_rol = SubmitField(_l("Guardar rol"))


class OtpVerificationForm(FlaskForm):
    """Formulario para verificar un código OTP de 6 dígitos."""

    code = StringField(_l("Código de verificación"), validators=[DataRequired(), Length(min=6, max=6)])
    verificar = SubmitField(_l("Verificar"))


class ForgotPasswordForm(FlaskForm):
    """Formulario para solicitar recuperación de contraseña."""

    email = StringField(_l("Correo electrónico"), validators=[DataRequired(), Email()])
    enviar = SubmitField(_l("Enviar enlace de recuperación"))


class ResetPasswordForm(FlaskForm):
    """Formulario para restablecer contraseña con token de recuperación."""

    new_password = PasswordField(_l("Nueva contraseña"), validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        _l("Confirmar contraseña"),
        validators=[DataRequired(), EqualTo("new_password", message=_l("Las contraseñas deben coincidir"))],
    )
    restablecer = SubmitField(_l("Restablecer contraseña"))
