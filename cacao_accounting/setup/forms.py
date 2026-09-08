# Copyright 2026
# Licensed under the Apache License, Version 2.0

"""Formularios para el asistente de configuración inicial."""

from cacao_accounting.i18n import _l
from flask_wtf import FlaskForm
from wtforms import HiddenField, RadioField, SelectField, StringField
from wtforms.fields import DateField
from wtforms.validators import DataRequired, Optional

from cacao_accounting.database import Entity
from cacao_accounting.setup.catalogs import (
    LANGUAGE_CHOICES,
    catalog_choices,
    entity_type_choices,
    country_choices,
    setup_texts,
)
from cacao_accounting.setup.service import available_catalog_files

CATALOG_CHOICES = [
    ("preexistente", _l("Usar catálogo contable preexistente")),
    ("en_cero", _l("Crear catálogo contable en cero")),
]
COUNTRY_CHOICES = country_choices("es")


class SetupLanguageForm(FlaskForm):
    """Formulario para seleccionar el idioma de la aplicación."""

    idioma = SelectField(_l("Idioma predeterminado"), choices=LANGUAGE_CHOICES, validators=[DataRequired()])
    step = HiddenField(default="1")


class SetupRegionalForm(FlaskForm):
    """Formulario para seleccionar los valores regionales del asistente."""

    pais = SelectField(_l("País predeterminado"), choices=COUNTRY_CHOICES, validators=[DataRequired()])
    moneda = SelectField(_l("Moneda predeterminada"), choices=[], validators=[DataRequired()])
    zona_horaria = SelectField(_l("Zona horaria"), choices=[], validators=[DataRequired()])
    step = HiddenField(default="2")

    def __init__(self, *args, **kwargs):
        """Inicializa el formulario regional con las monedas disponibles."""
        language = kwargs.pop("language", "es")
        currencies = kwargs.pop("currencies", None)
        super().__init__(*args, **kwargs)
        texts = setup_texts(language)
        self.pais.label.text = texts["country"]
        self.moneda.label.text = texts["currency"]
        self.zona_horaria.label.text = texts.get("timezone", "Zona horaria")
        self.pais.choices = country_choices(language)
        self.moneda.choices = currencies or []
        from cacao_accounting.setup.catalogs import timezone_choices

        self.zona_horaria.choices = timezone_choices()


class SetupCompanyForm(FlaskForm):
    """Formulario para capturar los datos de la entidad de la empresa."""

    id = StringField(_l("Código de empresa"), validators=[DataRequired()])
    razon_social = StringField(_l("Razón social"), validators=[DataRequired()])
    nombre_comercial = StringField(_l("Nombre comercial"))
    id_fiscal = StringField(_l("Identificación fiscal"), validators=[DataRequired()])
    tipo_entidad = SelectField(_l("Tipo de entidad"), choices=Entity.tipo_entidad_lista, validators=[DataRequired()])
    inicio_anio_fiscal = DateField(_l("Inicio Año Fiscal"), validators=[Optional()])
    fin_anio_fiscal = DateField(_l("Fin Año Fiscal"), validators=[Optional()])
    catalogo = RadioField(
        _l("Catálogo contable"),
        choices=CATALOG_CHOICES,
        default="preexistente",
        validators=[DataRequired()],
    )
    catalogo_origen = SelectField(_l("Catálogo existente"), choices=[], validators=[])
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
        self.tipo_entidad.choices = entity_type_choices(language)
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
