# Copyright 2026
# Licensed under the Apache License, Version 2.0

"""Pruebas unitarias para la configuración y lógica de Zona Horaria."""

import pytest
from flask import Flask, has_request_context
from cacao_accounting import create_app
from cacao_accounting.database import database, CacaoConfig
from cacao_accounting.setup.catalogs import (
    country_timezone_map,
    timezone_choices,
    setup_template_context,
)
from cacao_accounting.setup.forms import SetupRegionalForm
from cacao_accounting.setup.service import (
    save_regional_settings,
    get_setup_configuration,
    SETUP_TIMEZONE,
)


@pytest.fixture
def app_instance():
    """Crea una instancia de la aplicación para pruebas."""
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "testsecretkey",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with app.app_context():
        database.create_all()
        # Initialize default currencies
        from cacao_accounting.database import Currency
        nio = Currency(code="NIO", name="Córdoba Nicaragüense", decimals=2, active=True, default=True)
        usd = Currency(code="USD", name="Dólar Estadounidense", decimals=2, active=True, default=False)
        database.session.add(nio)
        database.session.add(usd)
        database.session.commit()
    yield app


def test_catalogs_timezone_logic():
    """Valida la lógica de zonas horarias en catálogos."""
    tz_map = country_timezone_map()
    assert isinstance(tz_map, dict)
    assert tz_map["NI"] == "America/Managua"
    assert tz_map["US"] == "America/New_York"
    assert tz_map["CR"] == "America/Costa_Rica"

    choices = timezone_choices()
    assert len(choices) > 0
    assert ("America/Managua", "America/Managua") in choices
    assert ("UTC", "UTC") in choices

    context = setup_template_context("es")
    assert "country_timezone_map" in context
    assert context["country_timezone_map"]["NI"] == "America/Managua"


def test_setup_regional_form(app_instance):
    """Valida el formulario regional con el nuevo campo de zona horaria."""
    with app_instance.test_request_context():
        form = SetupRegionalForm(language="es", currencies=[("NIO", "NIO")])
        assert "zona_horaria" in form
        assert form.zona_horaria.label.text == "Zona horaria"
        assert len(form.zona_horaria.choices) > 0


def test_save_and_retrieve_timezone(app_instance):
    """Valida guardar y recuperar zona horaria desde el servicio de configuración."""
    with app_instance.app_context():
        # Test default setup configuration (which should fall back to America/Managua)
        config = get_setup_configuration()
        assert config["zona_horaria"] == "America/Managua"

        # Save a new valid regional settings
        save_regional_settings("CR", "USD", "America/Costa_Rica")

        # Retrieve and verify
        config = get_setup_configuration()
        assert config["pais"] == "CR"
        assert config["moneda"] == "USD"
        assert config["zona_horaria"] == "America/Costa_Rica"

        # Invalid timezone should raise ValueError
        with pytest.raises(ValueError, match="La zona horaria seleccionada no es válida."):
            save_regional_settings("CR", "USD", "America/NonExistentTimeZone")


def test_global_timezone_selector(app_instance):
    """Valida que el selector global de Babel devuelva el valor correcto en contextos de request."""
    from flask_babel import get_timezone

    # With first request context
    with app_instance.test_request_context():
        # Default fallback
        tz = get_timezone()
        assert str(tz) == "America/Managua"

    # Save configuration in app context
    with app_instance.app_context():
        save_regional_settings("CR", "USD", "America/Costa_Rica")
        val = database.session.execute(database.select(CacaoConfig).filter_by(key="SETUP_TIMEZONE")).scalar_one_or_none()
        print("SETUP_TIMEZONE value in DB:", val.value if val else "None")

    # Retrieve again in a fresh request context
    with app_instance.test_request_context():
        tz = get_timezone()
        print("Retrieved get_timezone() in fresh request context:", str(tz))
        assert str(tz) == "America/Costa_Rica"
