# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1835: editar una conciliación conserva la cabecera y las observaciones.

La plantilla de conciliación no incluía un campo ``remarks`` y sus
``smart_select`` no recibían ``initial_value_expr``: el ``x-effect`` del
macro copiaba un valor vacío sobre ``header`` y el borrador perdía la
cuenta de ajuste, las dimensiones y las notas al reenviar el formulario.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser

from cacao_accounting.database import (
    Accounts,
    CostCenter,
    NamingSeries,
    Project,
    StockEntry,
    Unit,
    database,
)
from cacao_accounting.document_flow import currency_resolver
from cacao_accounting.inventario import services as inventory_services
from cacao_accounting.inventario.services import (
    _render_stock_reconciliation_edit_form,
    _update_stock_entry_from_form,
)

CAMPOS_CABECERA = (
    "company",
    "naming_series",
    "adjustment_account_id",
    "cost_center_code",
    "unit_code",
    "project_code",
)


class _ParserFormulario(HTMLParser):
    """Recoge la configuración del formulario y de cada smart_select."""

    def __init__(self) -> None:
        super().__init__()
        self.config_formulario = ""
        self.config_selects: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        valores = dict(attrs)
        config = valores.get("x-data") or ""
        if tag == "form" and config.startswith("stockReconciliationForm("):
            self.config_formulario = config
        elif config.startswith("smartSelect("):
            self.config_selects.append(config)


def _sembrar_maestros() -> None:
    """Crea los maestros referenciados por el borrador de conciliación."""
    database.session.add_all(
        [
            NamingSeries(
                name="SERIE-CONCIL-1835",
                entity_type="stock_entry",
                company="cacao",
                prefix_template="CONCIL-.####",
                is_active=True,
                is_default=False,
            ),
            Accounts(entity="cacao", code="1835", name="Cuenta ajuste 1835", classification="asset", group=False),
            CostCenter(code="CC-CONCIL", name="Centro 1835", entity="cacao"),
            Unit(code="UN-CONCIL", name="Unidad 1835", entity="cacao", enabled=True),
            Project(code="PRY-CONCIL", name="Proyecto 1835", entity="cacao", enabled=True),
        ]
    )
    database.session.flush()


def _borrador(**cambios) -> StockEntry:
    """Crea un borrador de conciliación con cabecera completa."""
    _sembrar_maestros()
    series = database.session.execute(database.select(NamingSeries).filter_by(name="SERIE-CONCIL-1835")).scalar_one()
    cuenta = database.session.execute(database.select(Accounts).filter_by(code="1835")).scalar_one()
    datos = {
        "company": "cacao",
        "purpose": "stock_reconciliation",
        "docstatus": 0,
        "remarks": "Reconteo diciembre",
        "transaction_currency": "NIO",
        "base_currency": "NIO",
        "naming_series_id": series.id,
        "adjustment_account_id": cuenta.id,
        "cost_center_code": "CC-CONCIL",
        "unit_code": "UN-CONCIL",
        "project_code": "PRY-CONCIL",
    }
    datos.update(cambios)
    entry = StockEntry(**datos)
    database.session.add(entry)
    database.session.commit()
    return entry


def _configuracion_cabecera(html: str) -> dict:
    """Extrae el header que la plantilla entrega al componente Alpine."""
    parser = _ParserFormulario()
    parser.feed(html)
    assert parser.config_formulario, "No se encontró stockReconciliationForm en la plantilla"
    inicio = parser.config_formulario.index("(") + 1
    config = json.loads(parser.config_formulario[inicio:-1])
    return config["header"]


def test_los_smart_select_inician_con_los_valores_del_borrador(app):
    """Cada selector recibe initialValue del header en lugar de un literal vacío."""
    with app.app_context():
        entry = _borrador()
        with app.test_request_context(f"/stock-entry/{entry.id}/edit"):
            html = _render_stock_reconciliation_edit_form(entry, [], [])
        cabecera = _configuracion_cabecera(html)
        database.session.rollback()

    parser = _ParserFormulario()
    parser.feed(html)
    assert len(parser.config_selects) == len(CAMPOS_CABECERA)
    for campo in CAMPOS_CABECERA:
        config = next((item for item in parser.config_selects if f'name: "{campo}"' in item), None)
        assert config is not None, f"falta el smart_select de {campo}"
        assert f"initialValue: header.{campo}" in config, config
        assert f"initialLabel: header.{campo}" in config, config
        assert cabecera[campo], f"{campo} no llegó al header renderizado"


def test_la_edicion_expone_las_observaciones_del_borrador(app):
    """La plantilla publica remarks y lo envía con el resto de la cabecera."""
    with app.app_context():
        entry = _borrador(remarks="Ajuste por merma autorizada")
        with app.test_request_context(f"/stock-entry/{entry.id}/edit"):
            html = _render_stock_reconciliation_edit_form(entry, [], [])
        cabecera = _configuracion_cabecera(html)
        database.session.rollback()

    assert cabecera["remarks"] == "Ajuste por merma autorizada"
    assert re.search(r'<input[^>]*name="remarks"[^>]*x-model="header\.remarks"', html)


def test_reenviar_la_cabecera_conserva_observaciones_y_dimensiones(app, monkeypatch):
    """Un POST de edición sin campos opcionales no borra los valores previos."""
    monkeypatch.setattr(inventory_services, "_validate_stock_entry_company", lambda _value, _action: "cacao")
    monkeypatch.setattr(inventory_services, "_validate_stock_entry_dimensions", lambda *_args: None)
    monkeypatch.setattr(inventory_services, "_validate_stock_entry_adjustment_account", lambda *_args: None)
    monkeypatch.setattr(currency_resolver, "company_functional_currency", lambda _company: "NIO")

    with app.app_context():
        entry = _borrador()
        esperado = (
            entry.remarks,
            entry.adjustment_account_id,
            entry.cost_center_code,
            entry.unit_code,
            entry.project_code,
            entry.naming_series_id,
        )
        with app.test_request_context(
            f"/stock-entry/{entry.id}/edit",
            method="POST",
            data={
                "purpose": "stock_reconciliation",
                "company": "cacao",
                "posting_date": "2026-11-20",
            },
        ):
            _update_stock_entry_from_form(entry)
        database.session.commit()
        database.session.refresh(entry)

        assert (
            entry.remarks,
            entry.adjustment_account_id,
            entry.cost_center_code,
            entry.unit_code,
            entry.project_code,
            entry.naming_series_id,
        ) == esperado
        database.session.rollback()


def test_limpiar_una_dimension_de_forma_explicita_la_borra(app, monkeypatch):
    """Preservar el valor ausente no impide limpiar una dimensión opcional."""
    monkeypatch.setattr(inventory_services, "_validate_stock_entry_company", lambda _value, _action: "cacao")
    monkeypatch.setattr(inventory_services, "_validate_stock_entry_dimensions", lambda *_args: None)
    monkeypatch.setattr(inventory_services, "_validate_stock_entry_adjustment_account", lambda *_args: None)
    monkeypatch.setattr(currency_resolver, "company_functional_currency", lambda _company: "NIO")

    with app.app_context():
        entry = _borrador()
        with app.test_request_context(
            f"/stock-entry/{entry.id}/edit",
            method="POST",
            data={
                "purpose": "stock_reconciliation",
                "company": "cacao",
                "posting_date": "2026-11-20",
                "cost_center_code": "",
                "project_code": "PRY-CONCIL",
            },
        ):
            _update_stock_entry_from_form(entry)
        database.session.commit()
        database.session.refresh(entry)

        assert entry.cost_center_code is None
        assert entry.project_code == "PRY-CONCIL"
        assert entry.remarks == "Reconteo diciembre"
        database.session.rollback()
