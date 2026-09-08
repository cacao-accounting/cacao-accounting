# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 William José Moreno Reyes

"""Pruebas de verificación de empaquetado de i18n y carga de traducciones.

Verifica que las traducciones (.po y .mo) se incluyan correctamente al construir el
paquete de distribución y que Flask-Babel cargue las traducciones del paquete activo.
"""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest
from flask_babel import force_locale, gettext

from cacao_accounting import _transaction_form_i18n_labels, create_app

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PACKAGE_ROOT / "dist"


@pytest.fixture(scope="module")
def app_instance():
    """Instancia de la aplicación Flask configurada para pruebas."""
    _app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "packaging_i18n_secret_key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
        }
    )
    return _app


def test_translations_loaded_in_english(app_instance) -> None:
    """Verifica que las cadenas transaccionales se traduzcan al inglés automáticamente."""
    with app_instance.test_request_context():
        with force_locale("en"):
            assert gettext("Solicitud de Compra") == "Purchase Request"
            assert gettext("Factura de Venta") == "Sales Invoice"
            assert gettext("Nota de Entrega") == "Delivery Note"
            assert gettext("Orden de Compra") == "Purchase Order"

            labels = _transaction_form_i18n_labels()
            assert labels["purchaseRequest"] == "Purchase Request"
            assert labels["salesInvoice"] == "Sales Invoice"


def test_translations_loaded_in_spanish(app_instance) -> None:
    """Verifica la resolución en español (idioma fuente/predeterminado)."""
    with app_instance.test_request_context():
        with force_locale("es"):
            assert gettext("Solicitud de Compra") == "Solicitud de Compra"
            assert gettext("Factura de Venta") == "Factura de Venta"

            labels = _transaction_form_i18n_labels()
            assert labels["purchaseRequest"] == "Solicitud de Compra"
            assert labels["salesInvoice"] == "Factura de Venta"


def test_built_distribution_contains_translation_catalogs() -> None:
    """Verifica que los artefactos construidos (.whl y .tar.gz) contengan .po y .mo."""
    wheels = list(DIST_DIR.glob("*.whl"))
    sdists = list(DIST_DIR.glob("*.tar.gz"))

    if not wheels or not sdists:
        pytest.skip("Artefactos en dist/ no construidos antes del test.")

    wheel_files: list[str] = []
    with zipfile.ZipFile(wheels[0]) as z:
        wheel_files = z.namelist()

    assert any("cacao_accounting/translations/en/LC_MESSAGES/messages.mo" in f for f in wheel_files)
    assert any("cacao_accounting/translations/en/LC_MESSAGES/messages.po" in f for f in wheel_files)
    assert any("cacao_accounting/translations/es/LC_MESSAGES/messages.mo" in f for f in wheel_files)
    assert any("cacao_accounting/translations/es/LC_MESSAGES/messages.po" in f for f in wheel_files)

    sdist_files: list[str] = []
    with tarfile.open(sdists[0]) as t:
        sdist_files = t.getnames()

    assert any("cacao_accounting/translations/en/LC_MESSAGES/messages.mo" in f for f in sdist_files)
    assert any("cacao_accounting/translations/en/LC_MESSAGES/messages.po" in f for f in sdist_files)
    assert any("cacao_accounting/translations/es/LC_MESSAGES/messages.mo" in f for f in sdist_files)
    assert any("cacao_accounting/translations/es/LC_MESSAGES/messages.po" in f for f in sdist_files)
