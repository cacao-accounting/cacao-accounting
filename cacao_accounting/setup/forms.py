# Copyright 2026
# Licensed under the Apache License, Version 2.0

"""Formularios para el asistente de configuración inicial."""

from flask_wtf import FlaskForm
from wtforms import HiddenField, RadioField, SelectField, StringField
from wtforms.fields import DateField
from wtforms.validators import DataRequired, Optional

from cacao_accounting.contabilidad.auxiliares import obtener_lista_monedas
from cacao_accounting.database import Entity
from cacao_accounting.setup.service import available_catalog_files

LANGUAGE_CHOICES = [
    ("es", "Español"),
    ("en", "English"),
    ("pt", "Português"),
]

COUNTRY_CHOICES = [
    ("NI", "Nicaragua"),
    ("US", "Estados Unidos"),
    ("MX", "México"),
    ("ES", "España"),
    ("CO", "Colombia"),
    ("PA", "Panamá"),
]

CATALOG_CHOICES = [
    ("preexistente", "Usar catálogo contable preexistente"),
    ("en_cero", "Crear catálogo contable en cero"),
]


class SetupLanguageForm(FlaskForm):
    """Formulario para seleccionar el idioma de la aplicación."""

    idioma = SelectField("Idioma predeterminado", choices=LANGUAGE_CHOICES, validators=[DataRequired()])
    step = HiddenField(default="1")


class SetupRegionalForm(FlaskForm):
    """Formulario para seleccionar los valores regionales del asistente."""

    pais = SelectField("País predeterminado", choices=COUNTRY_CHOICES, validators=[DataRequired()])
    moneda = SelectField("Moneda predeterminada", choices=[], validators=[DataRequired()])
    step = HiddenField(default="2")

    def __init__(self, *args, **kwargs):
        """Inicializa el formulario regional con las monedas disponibles."""
        super().__init__(*args, **kwargs)
        self.moneda.choices = obtener_lista_monedas()


class SetupCompanyForm(FlaskForm):
    """Formulario para capturar los datos de la entidad de la empresa."""

    id = StringField("Código de empresa", validators=[DataRequired()])
    razon_social = StringField("Razón social", validators=[DataRequired()])
    nombre_comercial = StringField("Nombre comercial")
    id_fiscal = StringField("Identificación fiscal", validators=[DataRequired()])
    tipo_entidad = SelectField("Tipo de entidad", choices=Entity.tipo_entidad_lista, validators=[DataRequired()])
    inicio_anio_fiscal = DateField("Inicio Año Fiscal", validators=[Optional()])
    fin_anio_fiscal = DateField("Fin Año Fiscal", validators=[Optional()])
    catalogo = RadioField(
        "Catálogo contable",
        choices=CATALOG_CHOICES,
        default="preexistente",
        validators=[DataRequired()],
    )
    catalogo_origen = SelectField("Catálogo existente", choices=[], validators=[])
    step = HiddenField(default="3")

    def __init__(self, *args, **kwargs):
        """Inicializa el formulario de empresa con las opciones de catálogo disponibles."""
        super().__init__(*args, **kwargs)
        self.catalogo_origen.choices = [("", "Seleccione un catálogo existente")] + available_catalog_files()


class SetupConfirmationForm(FlaskForm):
    """Formulario final de confirmación del proceso de configuración."""

    step = HiddenField(default="4")
