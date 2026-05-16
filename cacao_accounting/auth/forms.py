# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios del modulo de administración de sesión."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectMultipleField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional
from wtforms.widgets import CheckboxInput, ListWidget

SEGUNDO_NOMBRE = "Segundo Nombre"
SEGUNDO_APELLIDO = "Segundo Apellido"
CORREO_ELECTRONICO = "Correo electrónico"
TELEFONO = "Teléfono"
CONFIRMAR_CONTRASENA = "Confirmar contraseña"
CONTRASENAS_DEBEN_COINCIDIR = "Las contraseñas deben coincidir"


class LoginForm(FlaskForm):
    """Formulario de inicio de sesión."""

    usuario = StringField(validators=[DataRequired()])
    acceso = PasswordField(validators=[DataRequired()])
    inicio_sesion = SubmitField()


class ProfileForm(FlaskForm):
    """Formulario para actualizar información personal."""

    name = StringField("Nombre", validators=[Optional()])
    name2 = StringField(SEGUNDO_NOMBRE, validators=[Optional()])
    last_name = StringField("Apellido", validators=[Optional()])
    last_name2 = StringField(SEGUNDO_APELLIDO, validators=[Optional()])
    e_mail = StringField(CORREO_ELECTRONICO, validators=[Optional(), Email()])
    phone = StringField(TELEFONO, validators=[Optional()])
    guardar_perfil = SubmitField("Guardar cambios")


class PasswordChangeForm(FlaskForm):
    """Formulario para cambiar la contraseña del usuario."""

    current_password = PasswordField("Contraseña actual", validators=[DataRequired()])
    new_password = PasswordField("Nueva contraseña", validators=[DataRequired()])
    confirm_password = PasswordField(
        CONFIRMAR_CONTRASENA,
        validators=[DataRequired(), EqualTo("new_password", message=CONTRASENAS_DEBEN_COINCIDIR)],
    )
    cambiar_clave = SubmitField("Cambiar contraseña")


class UserCreateForm(FlaskForm):
    """Formulario para crear usuarios."""

    usuario = StringField("Usuario", validators=[DataRequired(), Length(min=3, max=15)])
    name = StringField("Nombre", validators=[Optional()])
    name2 = StringField(SEGUNDO_NOMBRE, validators=[Optional()])
    last_name = StringField("Apellido", validators=[Optional()])
    last_name2 = StringField(SEGUNDO_APELLIDO, validators=[Optional()])
    e_mail = StringField(CORREO_ELECTRONICO, validators=[Optional(), Email()])
    phone = StringField(TELEFONO, validators=[Optional()])
    classification = StringField("Clasificación", validators=[Optional()])
    active = BooleanField("Habilitado", default=True)
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        CONFIRMAR_CONTRASENA,
        validators=[DataRequired(), EqualTo("password", message=CONTRASENAS_DEBEN_COINCIDIR)],
    )
    crear_usuario = SubmitField("Crear usuario")


class UserEditForm(FlaskForm):
    """Formulario para editar usuarios."""

    usuario = StringField("Usuario", validators=[DataRequired(), Length(min=3, max=15)])
    name = StringField("Nombre", validators=[Optional()])
    name2 = StringField(SEGUNDO_NOMBRE, validators=[Optional()])
    last_name = StringField("Apellido", validators=[Optional()])
    last_name2 = StringField(SEGUNDO_APELLIDO, validators=[Optional()])
    e_mail = StringField(CORREO_ELECTRONICO, validators=[Optional(), Email()])
    phone = StringField(TELEFONO, validators=[Optional()])
    classification = StringField("Clasificación", validators=[Optional()])
    active = BooleanField("Habilitado")
    guardar_usuario = SubmitField("Guardar usuario")


class UserPasswordForm(FlaskForm):
    """Formulario para cambiar contraseña de usuario desde administración."""

    password = PasswordField("Nueva contraseña", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        CONFIRMAR_CONTRASENA,
        validators=[DataRequired(), EqualTo("password", message=CONTRASENAS_DEBEN_COINCIDIR)],
    )
    cambiar_clave = SubmitField("Cambiar contraseña")


class MultiCheckboxField(SelectMultipleField):
    """Campo para representar una lista de opciones con checkboxes."""

    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class UserRoleForm(FlaskForm):
    """Formulario para asignar roles a un usuario."""

    roles = MultiCheckboxField("Roles", validators=[Optional()], choices=[])
    guardar_roles = SubmitField("Guardar roles")


class RoleForm(FlaskForm):
    """Formulario para crear o editar un rol."""

    name = StringField("Nombre del rol", validators=[DataRequired(), Length(min=3, max=50)])
    note = StringField("Detalle", validators=[Optional(), Length(max=100)])
    guardar_rol = SubmitField("Guardar rol")
