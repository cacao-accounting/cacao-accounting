# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1865: el editor de StockEntry publica y conserva el origen documental.

La edición de una entrada vinculada compara la identidad de origen enviada por
el formulario con la persistida. El render debe hidratar ``source_type``,
``source_id`` y ``source_item_id`` de cada línea; de lo contrario una edición
de solo cabecera se rechaza como si el origen se hubiese eliminado.

Los casos usan una base SQLite aislada: la evidencia documental es append-only
y no debe borrarse durante el teardown de una prueba.
"""

import json
import re
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.database import DocumentRelation, StockEntry, StockEntryItem, User, database

_CONFIG_RE = re.compile(r"transactionForm\((.*?)\)'", re.DOTALL)


def _admin_client(app):
    """Cliente HTTP autenticado sobre la app aislada de la prueba."""
    with app.app_context():
        admin = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        user_id = str(admin.id)
        auth_version = admin.auth_version
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    return client


def _seed_linked_entry(app, relation_status: str = "active") -> dict[str, str]:
    """Crea un movimiento vinculado en la base aislada de la prueba."""
    suffix = uuid4().hex[:10]
    with app.app_context():
        from cacao_accounting.database import NamingSeries
        from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company

        ensure_default_naming_series_for_company("cacao", ["stock_entry"])
        database.session.commit()
        series_id = database.session.execute(
            database.select(NamingSeries.id).filter_by(entity_type="stock_entry", company="cacao")
        ).scalar_one()
        entry = StockEntry(
            company="cacao",
            purpose="material_receipt",
            posting_date=date(2026, 5, 15),
            transaction_currency="NIO",
            base_currency="NIO",
            naming_series_id=series_id,
            remarks="Original header",
        )
        database.session.add(entry)
        database.session.flush()
        line = StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ART01",
            qty=Decimal("2"),
            uom="UND",
            qty_in_base_uom=Decimal("2"),
            basic_rate=Decimal("10"),
            amount=Decimal("20"),
        )
        database.session.add(line)
        database.session.flush()
        relation = DocumentRelation(
            source_type="purchase_receipt",
            source_id=f"receipt-{suffix}",
            source_item_id=f"receipt-line-{suffix}",
            target_type="stock_entry",
            target_id=entry.id,
            target_item_id=line.id,
            company="cacao",
            qty=Decimal("2"),
            qty_in_base_uom=Decimal("2"),
            uom="UND",
            rate=Decimal("10"),
            amount=Decimal("20"),
            relation_type="purchase_receipt_to_stock_entry",
            status=relation_status,
        )
        database.session.add(relation)
        database.session.commit()
        return {
            "entry": entry.id,
            "line": line.id,
            "relation": relation.id,
            "source_type": relation.source_type,
            "source_id": relation.source_id,
            "source_item_id": relation.source_item_id,
        }


def _seed_second_company(app) -> tuple[str, str]:
    """Crea otra compañía accesible por el usuario para probar el cambio de compañía."""
    from cacao_accounting.database import Entity, NamingSeries, UserCompanyAccess
    from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company

    code = f"OT{uuid4().hex[:6]}"
    with app.app_context():
        user_id = str(database.session.execute(select(User.id).filter_by(user="admin")).scalar_one())
        database.session.add(
            Entity(
                code=code,
                company_name=f"Compañía Alterna {code}",
                name=f"Compañía Alterna {code}",
                tax_id=f"TAX-{code}",
                currency="NIO",
                enabled=True,
            )
        )
        database.session.add(UserCompanyAccess(user_id=user_id, company_code=code))
        database.session.commit()
        ensure_default_naming_series_for_company(code, ["stock_entry"])
        database.session.commit()
        series_id = database.session.execute(
            database.select(NamingSeries.id).filter_by(entity_type="stock_entry", company=code)
        ).scalar_one()
    return code, series_id


def _edit_config(client, entry_id: str) -> dict:
    """Obtiene la configuración que el servidor entrega al formulario de edición."""
    response = client.get(f"/inventory/stock-entry/{entry_id}/edit")
    assert response.status_code == 200
    match = _CONFIG_RE.search(response.get_data(as_text=True))
    assert match is not None, "el formulario de edición no publica transactionForm"
    return json.loads(match.group(1))


def _form_from_render(config: dict, **header_overrides: str) -> dict[str, str]:
    """Construye el POST tal como lo enviaría el navegador desde el render."""
    header = config["initialHeader"]
    form: dict[str, str] = {
        "purpose": "material_receipt",
        "company": header.get("company") or "cacao",
        "naming_series": header.get("naming_series", ""),
        "currency": header.get("currency", "NIO"),
        "transaction_currency": header.get("currency", "NIO"),
        "posting_date": "2026-05-16",
        "remarks": "Edited header",
    }
    form.update(header_overrides)
    for index, line in enumerate(config["initialLines"]):
        for field in (
            "item_code",
            "qty",
            "uom",
            "rate",
            "amount",
            "batch_id",
            "serial_no",
            "source_warehouse",
            "target_warehouse",
            "source_type",
            "source_id",
            "source_item_id",
        ):
            form[f"{field}_{index}"] = str(line.get(field, ""))
    return form


@pytest.mark.parametrize("relation_status", ["active", "closed"])
def test_edit_render_hydrates_line_origin(entorno_contable_aislado, relation_status):
    """El GET de edición publica el origen persistido de cada línea vinculada."""
    app = entorno_contable_aislado.app
    ids = _seed_linked_entry(app, relation_status)
    config = _edit_config(_admin_client(app), ids["entry"])

    assert config["initialLines"]
    line = config["initialLines"][0]
    assert line["source_type"] == ids["source_type"]
    assert line["source_id"] == ids["source_id"]
    assert line["source_item_id"] == ids["source_item_id"]


def test_header_edit_from_rendered_form_preserves_relation(entorno_contable_aislado):
    """El POST derivado del render real guarda la cabecera y conserva la relación."""
    app = entorno_contable_aislado.app
    ids = _seed_linked_entry(app, "active")
    client = _admin_client(app)
    form = _form_from_render(_edit_config(client, ids["entry"]))

    response = client.post(f"/inventory/stock-entry/{ids['entry']}/edit", data=form)

    assert response.status_code == 302
    with app.app_context():
        saved_entry = database.session.get(StockEntry, ids["entry"])
        saved_line = database.session.get(StockEntryItem, ids["line"])
        saved_relation = database.session.get(DocumentRelation, ids["relation"])
        assert saved_entry is not None
        assert (saved_entry.remarks, saved_entry.posting_date) == ("Edited header", date(2026, 5, 16))
        assert saved_line is not None and saved_line.id == ids["line"]
        assert saved_relation is not None
        assert saved_relation.target_item_id == ids["line"]


def test_header_edit_rejects_company_change_without_mutating_evidence(entorno_contable_aislado):
    """Cambiar la compañía de una entrada vinculada se rechaza antes de tocar evidencia."""
    app = entorno_contable_aislado.app
    ids = _seed_linked_entry(app, "active")
    client = _admin_client(app)
    other_company, other_series = _seed_second_company(app)
    form = _form_from_render(_edit_config(client, ids["entry"]), company=other_company, naming_series=other_series)

    response = client.post(f"/inventory/stock-entry/{ids['entry']}/edit", data=form)

    assert response.status_code == 200
    assert "No se puede cambiar la compañía" in response.get_data(as_text=True)
    with app.app_context():
        saved_entry = database.session.get(StockEntry, ids["entry"])
        saved_relation = database.session.get(DocumentRelation, ids["relation"])
        assert saved_entry is not None and saved_entry.company == "cacao"
        assert saved_entry.remarks == "Original header"
        assert saved_relation is not None and saved_relation.target_item_id == ids["line"]
