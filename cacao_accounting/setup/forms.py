# Copyright 2026
# Licensed under the Apache License, Version 2.0

"""Formularios para el asistente de configuración inicial."""

from flask_wtf import FlaskForm
from wtforms import HiddenField, RadioField, SelectField, StringField
from wtforms.fields import DateField
from wtforms.validators import DataRequired, Optional

from cacao_accounting.database import Entity
from cacao_accounting.setup.catalogs import (
    LANGUAGE_CHOICES,
    catalog_choices,
    country_choices,
    setup_texts,
)
from cacao_accounting.setup.service import available_catalog_files

CATALOG_CHOICES = [
    ("preexistente", "Usar catálogo contable preexistente"),
    ("en_cero", "Crear catálogo contable en cero"),
]
COUNTRY_CHOICES = country_choices("es")


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
        language = kwargs.pop("language", "es")
        currencies = kwargs.pop("currencies", None)
        super().__init__(*args, **kwargs)
        texts = setup_texts(language)
        self.pais.label.text = texts["country"]
        self.moneda.label.text = texts["currency"]
        self.pais.choices = country_choices(language)
        self.moneda.choices = currencies or []


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
        language = kwargs.pop("language", "es")
        super().__init__(*args, **kwargs)
        texts = setup_texts(language)
        self.id.label.text = texts["company_code"]
        self.razon_social.label.text = texts["legal_name"]
        self.nombre_comercial.label.text = texts["trade_name"]
        self.id_fiscal.label.text = texts["tax_id"]
        self.tipo_entidad.label.text = texts["entity_type"]
        self.inicio_anio_fiscal.label.text = texts["fiscal_year_start"]
        self.fin_anio_fiscal.label.text = texts["fiscal_year_end"]
        self.catalogo.label.text = texts["catalog_title"]
        self.catalogo.choices = catalog_choices(language)
        self.catalogo_origen.label.text = texts["existing_catalog"]
        self.catalogo_origen.choices = [("", texts["select_catalog"])] + available_catalog_files()
        if self.catalogo.data == "en_cero":
            self.catalogo_origen.data = ""


class SetupConfirmationForm(FlaskForm):
    """Formulario final de confirmación del proceso de configuración."""

    step = HiddenField(default="4")
