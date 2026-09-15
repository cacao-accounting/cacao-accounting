# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Guarda de calidad del catálogo inglés de i18n.

Cubre regresiones detectadas en producción:

- Etiquetas que se traducen en runtime con ``_(variable)`` (por ejemplo los
  estados calculados en ``document_flow/status.py``) no pueden ser extraídas
  por Babel, así que deben mantenerse manualmente en el catálogo.
- Traducciones a medio terminar (Spanglish) donde parte del ``msgstr`` quedó
  en español.
- Entradas ``fuzzy`` activas y placeholders que no se conservan entre el
  ``msgid`` y el ``msgstr``.
"""

from __future__ import annotations

import ast
from gettext import NullTranslations
import re
import shutil
import subprocess
from pathlib import Path

try:
    import polib
except ImportError:
    polib = None

import pytest
from flask import Flask
from flask_babel import Babel, force_locale
from babel.messages.pofile import read_po
from babel.support import Translations

from cacao_accounting.admin.navigation import CONFIGURATION_SECTIONS

TRANSLATIONS_DIR = Path(__file__).resolve().parent.parent / "cacao_accounting" / "translations"
PO_PATH = TRANSLATIONS_DIR / "en" / "LC_MESSAGES" / "messages.po"
SOURCE_DIR = TRANSLATIONS_DIR.parent
GETTEXT_HELPERS = frozenset({"_", "_l", "gettext", "lazy_gettext", "ngettext", "pgettext", "npgettext"})

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
def english_catalog() -> NullTranslations:
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
        (
            "Cree un lote para cargar plantillas CSV, XLSX, XLS u ODS.",
            "Create a batch to load CSV, XLSX, XLS, or ODS templates.",
        ),
        ("Inactivo; conserva historial y requiere motivo.", "Inactive; keeps history and requires a reason."),
        ("Extractos Bancarios", "Bank Statements"),
        ("Contabilidad y Maestros", "Accounting and Master Data"),
    ],
)
def test_reported_spanglish_strings_are_translated(english_catalog, msgid, expected):
    """Cadenas reportadas con Spanglish quedan correctamente traducidas."""
    assert english_catalog.gettext(msgid) == expected


@pytest.mark.parametrize(
    ("msgid", "expected"),
    [
        ("Validación externa de documentos", "External Document Validation"),
        ("Variación manual de entradas", "Manual inflow variance"),
        ("Actual (ERP + CxC/CxP)", "Current (ERP + AR/AP)"),
        ("Importar costos de importación", "Import landed costs"),
        ("Conciliación de existencias", "Stock reconciliation"),
        ("Artículos", "Items"),
        ("Predeterminada", "Default"),
        ("en curso", "In progress"),
        (
            "Se ha cancelado la Nota de Entrega %(document)s asociada.",
            "The associated Delivery Note %(document)s has been cancelled.",
        ),
        (
            "La versión '%(version)s' ya existe para este año fiscal.",
            "Version '%(version)s' already exists for this fiscal year.",
        ),
        (
            "La cuenta contable seleccionada no está activa o es una cuenta agrupadora.",
            "The selected accounting account is not active or is a grouping account.",
        ),
        ("No hay gastos pendientes para esta caja.", "No pending expenses for this petty cash fund."),
        ("Almacén predeterminado", "Default warehouse"),
        (
            "Puede incluir columnas con nombres alternativos (ej: Artículo, Producto, Código).",
            "You can include columns with alternative names (e.g.: Item, Product, Code).",
        ),
    ],
)
def test_new_source_spanish_messages_have_english_catalog_entries(msgid, expected):
    """Los textos normalizados al español conservan su traducción inglesa."""
    with PO_PATH.open("rb") as catalog_file:
        catalog = read_po(catalog_file)

    assert catalog.get(msgid).string == expected


def test_catalog_has_no_spanish_leftovers():
    """Ningún msgstr en inglés conserva palabras que sólo existen en español."""
    if polib is None:
        pytest.skip("polib is not installed")
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


def test_catalog_has_no_empty_active_english_translations() -> None:
    """Cada entrada activa del catálogo inglés debe tener una traducción."""
    if polib is None:
        pytest.skip("polib is not installed")
    empty_entries = [
        entry.msgid
        for entry in polib.pofile(str(PO_PATH))
        if not entry.obsolete
        and entry.msgid
        and ((not entry.msgid_plural and not entry.msgstr) or (entry.msgid_plural and not any(entry.msgstr_plural.values())))
    ]
    assert empty_entries == []


def test_catalog_has_no_active_fuzzy_entries() -> None:
    """Ninguna entrada activa del catálogo puede quedar marcada como ``fuzzy``."""
    if polib is None:
        pytest.skip("polib is not installed")
    fuzzy_entries = [entry.msgid for entry in polib.pofile(str(PO_PATH)) if not entry.obsolete and entry.fuzzy]
    assert fuzzy_entries == [], f"Entradas fuzzy activas: {fuzzy_entries}"


def test_catalog_placeholders_are_consistent_between_msgid_and_msgstr() -> None:
    """El ``msgstr`` debe conservar los placeholders posicionales del ``msgid``."""
    if polib is None:
        pytest.skip("polib is not installed")
    placeholder = re.compile(r"%\((\w+)\)")
    offenders = []
    for entry in polib.pofile(str(PO_PATH)):
        if entry.obsolete or not entry.msgid:
            continue
        msgid_placeholders = set(placeholder.findall(entry.msgid))
        msgstr_placeholders = set(placeholder.findall(entry.msgstr))
        for value in entry.msgstr_plural.values():
            msgstr_placeholders |= set(placeholder.findall(value))
        if msgid_placeholders != msgstr_placeholders:
            offenders.append((entry.msgid, sorted(msgid_placeholders), sorted(msgstr_placeholders)))
    assert offenders == [], f"Placeholders inconsistentes entre msgid y msgstr: {offenders}"


def test_catalog_raw_folding_roundtrips_through_polib() -> None:
    """El doblado crudo de ``msgid``/``msgstr`` no pierde ni altera contenido."""
    if polib is None:
        pytest.skip("polib is not installed")

    entries = [entry for entry in polib.pofile(str(PO_PATH)) if not entry.obsolete]
    lines = PO_PATH.read_text(encoding="utf-8").splitlines()
    problems: list[tuple[str, str, str]] = []
    index = 0
    target: str | None = None
    fragments: list[str] = []
    msgstr_fragments: list[str] = []

    def close_entry() -> None:
        nonlocal index, target, fragments, msgstr_fragments
        if target is None:
            return
        msgid = polib.unescape("".join(fragments))
        msgstr = polib.unescape("".join(msgstr_fragments))
        if not msgid:
            target = None
            fragments = []
            msgstr_fragments = []
            return
        if index < len(entries):
            expected = entries[index]
            if msgid != expected.msgid or msgstr != expected.msgstr:
                problems.append((expected.msgid, msgid, msgstr))
            index += 1
        target = None
        fragments = []
        msgstr_fragments = []

    def _strip_po_quotes(text: str) -> str:
        s = text.strip()
        if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
            return s[1:-1]
        return s

    for line in lines:
        if line.startswith("#") or line == "":
            close_entry()
            continue
        stripped = line.strip()
        if stripped.startswith("msgid "):
            close_entry()
            target = "msgid"
            fragments = [_strip_po_quotes(stripped[len("msgid ") :])]
            msgstr_fragments = []
            continue
        if stripped.startswith("msgstr "):
            target = "msgstr"
            msgstr_fragments = [_strip_po_quotes(stripped[len("msgstr ") :])]
            continue
        if target == "msgid":
            fragments.append(_strip_po_quotes(stripped))
        elif target == "msgstr":
            msgstr_fragments.append(_strip_po_quotes(stripped))
    close_entry()

    assert problems == [], f"El doblado crudo no coincide con el catálogo parseado: {problems}"


def test_catalog_passes_gettext_validation() -> None:
    """El catálogo no puede contener definiciones duplicadas para msgfmt."""
    msgfmt = shutil.which("msgfmt")
    if msgfmt is None:
        pytest.skip("msgfmt is not installed")
    result = subprocess.run([msgfmt, "--check", str(PO_PATH)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_configuration_navigation_labels_resolve_lazily_in_the_current_locale() -> None:
    """Las etiquetas configuradas al importar el módulo se resuelven por locale."""
    assert all(not isinstance(section.label, str) for section in CONFIGURATION_SECTIONS)

    app = Flask(__name__)
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = str(TRANSLATIONS_DIR)
    Babel(app, locale_selector=lambda: "es")

    with app.test_request_context():
        spanish = [str(section.label) for section in CONFIGURATION_SECTIONS]
        with force_locale("en"):
            english = [str(section.label) for section in CONFIGURATION_SECTIONS]

    assert all(value for value in english)
    assert all(en != es for en, es in zip(english, spanish))


def test_gettext_is_never_called_with_an_interpolated_f_string() -> None:
    """Babel debe recibir una plantilla literal antes de interpolar valores."""
    offenders = []
    for path in SOURCE_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and (
                    (isinstance(node.func, ast.Name) and node.func.id in GETTEXT_HELPERS)
                    or (isinstance(node.func, ast.Attribute) and node.func.attr in GETTEXT_HELPERS)
                )
                and node.args
                and isinstance(node.args[0], ast.JoinedStr)
            ):
                offenders.append(f"{path.relative_to(SOURCE_DIR.parent)}:{node.lineno}")
    assert offenders == [], f"gettext recibió f-strings ya interpolados: {offenders}"


def test_gettext_is_not_evaluated_at_module_or_class_initialization() -> None:
    """Las etiquetas configuradas fuera de funciones deben usar ``_l``."""
    offenders = []
    for path in SOURCE_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_" and node.args):
                continue
            current: ast.AST = node
            while current in parents:
                current = parents[current]
                if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    break
                if isinstance(current, ast.Module):
                    offenders.append(f"{path.relative_to(SOURCE_DIR.parent)}:{node.lineno}")
                    break
    assert offenders == [], f"gettext fue evaluado al importar módulos: {offenders}"
