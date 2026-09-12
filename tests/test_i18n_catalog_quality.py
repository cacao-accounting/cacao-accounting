# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Guarda de calidad del catálogo inglés de i18n.

Cubre dos regresiones detectadas en producción:

- Etiquetas que se traducen en runtime con ``_(variable)`` (por ejemplo los
  estados calculados en ``document_flow/status.py``) no pueden ser extraídas
  por Babel, así que deben mantenerse manualmente en el catálogo.
- Traducciones a medio terminar (Spanglish) donde parte del ``msgstr`` quedó
  en español.
"""

from __future__ import annotations

import re
from pathlib import Path

import polib
import pytest
from babel.support import Translations

TRANSLATIONS_DIR = Path(__file__).resolve().parent.parent / "cacao_accounting" / "translations"
PO_PATH = TRANSLATIONS_DIR / "en" / "LC_MESSAGES" / "messages.po"

SPANISH_ONLY_WORDS = {
    "transacciones",
    "recepciones",
    "facturar",
    "plantillas",
    "recurrentes",
    "aplicables",
    "conversiones",
    "filtros",
    "seleccionados",
    "tareas",
    "archivos",
    "adjuntos",
    "existencia",
    "reportes",
    "compania",
    "companías",
    "asientos",
    "proveedores",
    "clasificacion",
    "bodegas",
    "movimientos",
    "pendientes",
    "configuracion",
    "predeterminada",
    "representante",
    "vencimiento",
    "observaciones",
    "contador",
    "entidad",
    "borrador",
    "vencimiento",
}


@pytest.fixture(scope="module")
def english_catalog() -> Translations:
    """Catálogo compilado en inglés usado por la aplicación."""
    return Translations.load(str(TRANSLATIONS_DIR), "en")


@pytest.mark.parametrize(
    ("msgid", "expected"),
    [
        ("Requiere Atención", "Requires Attention"),
        ("Pendiente de Aprobación", "Pending Approval"),
        ("Anulación Pendiente", "Pending Cancellation"),
        ("Pagado", "Paid"),
        ("Pagado Parcialmente", "Partially Paid"),
        ("Pendiente Pagar", "Pending Payment"),
        ("Pendiente Cobrar", "Pending Collection"),
        ("Recibido Parcialmente", "Partially Received"),
        ("Pendiente Recibir", "Pending Receipt"),
        ("Entregado Parcialmente", "Partially Delivered"),
        ("Pendiente Entregar", "Pending Delivery"),
        ("Facturado Parcialmente", "Partially Billed"),
        ("Pendiente Facturar", "Pending Billing"),
    ],
)
def test_document_status_labels_translate(english_catalog, msgid, expected):
    """Los estados calculados por variable se resuelven en inglés."""
    assert english_catalog.gettext(msgid) == expected


@pytest.mark.parametrize(
    ("msgid", "expected"),
    [
        ("Cuentas Bancarias", "Bank Accounts"),
        ("Importar Extracto Bancario", "Import Bank Statement"),
        ("Existencia de Inventario", "Inventory Stock"),
        ("Mostrar anulaciones y reversas", "Show cancellations and reversals"),
        ("Cree un lote para cargar plantillas CSV, XLSX, XLS u ODS.", "Create a batch to load CSV, XLSX, XLS, or ODS templates."),
        ("Inactivo; conserva historial y requiere motivo.", "Inactive; keeps history and requires a reason."),
        ("Extractos Bancarios", "Bank Statements"),
        ("Contabilidad y Maestros", "Accounting and Master Data"),
    ],
)
def test_reported_spanglish_strings_are_translated(english_catalog, msgid, expected):
    """Cadenas reportadas con Spanglish quedan correctamente traducidas."""
    assert english_catalog.gettext(msgid) == expected


def test_catalog_has_no_spanish_leftovers():
    """Ningún msgstr en inglés conserva palabras que sólo existen en español."""
    word = re.compile(r"[A-Za-zÁÉÍÓÚÜáéíóúüÑñ]{4,}")
    offenders = []
    for entry in polib.pofile(str(PO_PATH)):
        if not entry.msgstr:
            continue
        words = {token.lower() for token in word.findall(entry.msgstr)}
        leftovers = sorted(words & SPANISH_ONLY_WORDS)
        if leftovers:
            offenders.append((entry.msgid, entry.msgstr, leftovers))
    assert offenders == [], f"Traducciones con Spanglish: {offenders}"
