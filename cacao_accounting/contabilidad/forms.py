# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Formularios web del modulo de contabilidad."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask_wtf import FlaskForm
from wtforms import SelectField, StringField
from wtforms.validators import DataRequired

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.database import Entity
from cacao_accounting.modulos import lista_tipos_documentos

# <------------------------------------------------------------------------------------------------------------------------> #
# Entidades


class FormularioEntidad(FlaskForm):
    """
    Formulario base para la administración de entidades.

    Este formulario este vinculada la la tabla Entidad en la base de datos y debe contener
    un mapeo de la mayoria de sus campos.
    """

    id = StringField(validators=[DataRequired()])
    razon_social = StringField(validators=[DataRequired()])
    nombre_comercial = StringField(validators=[])
    id_fiscal = StringField(validators=[DataRequired()])
    moneda = SelectField(
        "Tipo de Entidad",
    )
    tipo_entidad = SelectField("Tipo de Entidad", choices=Entity.tipo_entidad_lista)
    correo_electronico = StringField(validators=[])
    web = StringField(validators=[])
    telefono1 = StringField(validators=[])
    telefono2 = StringField(validators=[])
    fax = StringField(validators=[])


# <------------------------------------------------------------------------------------------------------------------------> #
# Unidades
class FormularioUnidad(FlaskForm):
    """
    Formulario base para la administración de unidades de negocio.

    Este formulario este vinculada la la tabla Unidad en la base de datos y debe contener
    un mapeo de la mayoria de sus campos.
    """

    id = StringField(validators=[DataRequired()])
    nombre = StringField(validators=[DataRequired()])
    entidad = SelectField("Entidad")
    correo_electronico = StringField(validators=[])
    web = StringField(validators=[])
    telefono1 = StringField(validators=[])
    telefono2 = StringField(validators=[])
    fax = StringField(validators=[])


class FormularioLibro(FlaskForm):
    """Formulario base para la administración de libros de contabilidad."""

    id = StringField(validators=[DataRequired()])
    nombre = StringField(validators=[DataRequired()])
    entidad = SelectField("Entidad")


# <------------------------------------------------------------------------------------------------------------------------> #
# Comprobantes Contables
class ComprobanteContable(FlaskForm):
    """Comprobante contable manual."""


class ComprobanteContableDetalle(FlaskForm):
    """Detalle de comprobante contable manual."""


# <------------------------------------------------------------------------------------------------------------------------> #
# Series e Identificadores
class FormularioSerie(FlaskForm):
    """Serie."""

    entidad = SelectField(
        "Entidad",
    )
    documento = SelectField("Documento", choices=lista_tipos_documentos())
    serie = StringField(validators=[])
