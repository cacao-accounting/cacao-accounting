# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas del contrato de internacionalización entre el backend y el frontend.

Verifica que las claves generadas por ``_transaction_form_i18n_labels`` (camelCase)
coincidan exactamente con las que consume ``static/js/transaction-form.js`` vía
``globalThis.__TXF_I18N__`` y que el JSON renderizado en ``base.html`` resuelva las
traducciones con el catálogo activo de Flask-Babel.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
from flask import Flask, render_template_string
from flask_babel import Babel

from cacao_accounting import _transaction_form_i18n_labels

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = PACKAGE_ROOT / "cacao_accounting" / "__init__.py"
BASE_TEMPLATE_FILE = PACKAGE_ROOT / "cacao_accounting" / "templates" / "base.html"
JS_FILE = PACKAGE_ROOT / "cacao_accounting" / "static" / "js" / "transaction-form.js"
TRANSLATIONS_DIR = PACKAGE_ROOT / "cacao_accounting" / "translations"

JS_I18N_KEYS = set(re.findall(r"\bi18n\.([A-Za-z0-9_]+)", JS_FILE.read_text()))


def _python_keys() -> set[str]:
    """Extrae las claves del dict retornado por ``_transaction_form_i18n_labels``."""
    source = INIT_FILE.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_transaction_form_i18n_labels":
            for stmt in node.body:
                if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Dict):
                    return {key.value for key in stmt.value.keys}
    raise AssertionError("No se encontró la función _transaction_form_i18n_labels")


def _msgids() -> dict[str, str]:
    """Devuelve el msgid de cada clave del diccionario de traducción."""
    source = INIT_FILE.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_transaction_form_i18n_labels":
            for stmt in node.body:
                if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Dict):
                    output: dict[str, str] = {}
                    for key, value in zip(stmt.value.keys, stmt.value.values):
                        if isinstance(value, ast.Call) and value.args:
                            argument = value.args[0]
                            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                                output[key.value] = argument.value
                    return output
    raise AssertionError("No se encontró la función _transaction_form_i18n_labels")


def _render_labels(locale: str) -> dict[str, str]:
    """Renderiza el JSON real que base.html inyecta al navegador para un idioma."""
    app = Flask(__name__)
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = str(TRANSLATIONS_DIR)
    Babel(app, locale_selector=lambda: locale)
    app.jinja_env.globals["transaction_form_i18n"] = _transaction_form_i18n_labels
    with app.test_request_context():
        rendered = render_template_string("{{ transaction_form_i18n() | tojson }}")
        return json.loads(rendered)


def test_backend_keys_are_camel_case() -> None:
    """Las claves del backend deben ser camelCase (contrato con el JavaScript)."""
    keys = _python_keys()
    assert keys, "No se extrajeron claves del backend"
    for key in keys:
        assert key[0].islower(), f"La clave '{key}' no inicia en minúscula"
        assert "_" not in key, f"La clave '{key}' no usa camelCase"


def test_js_and_backend_contract_keys_match() -> None:
    """El JS y el backend deben exponer exactamente el mismo conjunto de claves."""
    python_keys = _python_keys()
    missing = python_keys - JS_I18N_KEYS
    unknown = JS_I18N_KEYS - python_keys
    assert not unknown, f"El JS accede a claves que el backend no entrega: {sorted(unknown)}"
    assert not missing, f"El backend emite claves que el JS no consume: {sorted(missing)}"


def test_batch_and_serial_keep_item_code_placeholder() -> None:
    """Los mensajes de lote y serie deben conservar el placeholder {item_code}."""
    msgids = _msgids()
    assert "{item_code}" in msgids["errorBatchRequired"]
    assert "{item_code}" in msgids["errorSerialRequired"]


def test_base_template_injects_i18n_global() -> None:
    """base.html debe exponer el objeto de traducción al frontend."""
    source = BASE_TEMPLATE_FILE.read_text()
    assert "transaction_form_i18n()" in source
    assert "globalThis.__TXF_I18N__" in source


def test_rendered_json_uses_spanish_source_without_catalog() -> None:
    """En español (idioma fuente) los msgid se muestran tal cual."""
    labels = _render_labels("es")
    assert set(labels.keys()) == _python_keys()
    assert labels["purchaseRequest"] == "Solicitud de Compra"
    assert labels["errorBatchRequired"] == "El item {item_code} requiere lote."


def test_rendered_json_translates_to_english() -> None:
    """En inglés el JSON debe resolver las traducciones del catálogo en/messages.mo."""
    labels = _render_labels("en")
    assert set(labels.keys()) == _python_keys()
    assert labels["purchaseRequest"] == "Purchase Request"
    assert labels["errorBatchRequired"] == "The item {item_code} requires a batch."
    assert labels["errorSerialRequired"] == "The item {item_code} requires a serial number."


@pytest.mark.parametrize(
    "key",
    [
        "purchaseRequest",
        "purchaseQuotation",
        "supplierQuotation",
        "purchaseOrder",
        "purchaseReceipt",
        "purchaseInvoice",
        "salesRequest",
        "salesQuotation",
        "salesOrder",
        "deliveryNote",
        "salesInvoice",
        "stockEntry",
        "itemCodeLabel",
        "itemNameLabel",
        "uomLabel",
        "qtyLabel",
        "rateLabel",
        "amountLabel",
        "errorLoadingSource",
        "errorCurrencyRequired",
        "errorLinesRequired",
        "errorBatchRequired",
        "errorSerialRequired",
        "errorTaxPreview",
        "errorLoadingSourceStep",
        "manualTaxConcept",
    ],
)
def test_english_catalog_has_translation_for_every_key(key: str) -> None:
    """El catálogo en debe traducir todos los mensajes del formulario transaccional."""
    labels = _render_labels("en")
    assert labels[key] != _msgids()[key], f"'{key}' no tiene traducción al inglés"
