# SPDX-License-Identifier: Apache-2.0
"""#2324: rutas admin validan referencias antes de persistir.

Cubre impuestos, plantillas de impuestos, ?tems de plantilla y valores de dimensi?n.
Las referencias inv?lidas deben responder con redirect+flash y no mutar la base.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import (
    DimensionType,
    DimensionValue,
    Modules,
    Tax,
    TaxTemplate,
    TaxTemplateItem,
    database,
)


@pytest.fixture
def modulo_admin_activo(app):
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is None:
            modulo = Modules(module="admin", default=False, enabled=True)
            database.session.add(modulo)
            creado = True
            previo = True
        else:
            creado = False
            previo = bool(modulo.enabled)
            modulo.enabled = True
        database.session.commit()
    yield
    with app.app_context():
        modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if modulo is not None:
            if creado:
                database.session.delete(modulo)
            else:
                modulo.enabled = previo
            database.session.commit()


def _msg(response) -> str:
    return response.get_data(as_text=True)


def test_tax_rechaza_cuenta_inexistente(app, authenticated_client, modulo_admin_activo):
    name = f"Tax bad acct {uuid4().hex[:8]}"
    bad_account = f"NOPE-{uuid4().hex[:8]}"
    resp = authenticated_client("admin").post(
        "/settings/taxes",
        data={"name": name, "rate": "10", "tax_type": "percentage", "applies_to": "both", "account_id": bad_account},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "cuenta contable seleccionada no es v?lida" in _msg(resp).lower() or "no es v" in _msg(resp).lower()
    with app.app_context():
        assert database.session.execute(database.select(Tax).filter_by(name=name)).scalar_one_or_none() is None


def test_tax_template_rechaza_company_y_currency_invalidas(app, authenticated_client, modulo_admin_activo):
    client = authenticated_client("admin")

    bad_company_name = f"Tpl bad co {uuid4().hex[:8]}"
    resp = client.post(
        "/settings/tax-templates",
        data={"name": bad_company_name, "company": f"ZZ{uuid4().hex[:6]}", "template_type": "selling", "currency": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "compa??a seleccionada no es v?lida" in _msg(resp).lower() or "compa" in _msg(resp).lower()
    with app.app_context():
        row = database.session.execute(database.select(TaxTemplate).filter_by(name=bad_company_name)).scalar_one_or_none()
        assert row is None

    bad_currency_name = f"Tpl bad cur {uuid4().hex[:8]}"
    resp = client.post(
        "/settings/tax-templates",
        data={"name": bad_currency_name, "company": "", "template_type": "selling", "currency": "ZZZ"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "moneda seleccionada no es v?lida" in _msg(resp).lower() or "moneda" in _msg(resp).lower()
    with app.app_context():
        row = database.session.execute(database.select(TaxTemplate).filter_by(name=bad_currency_name)).scalar_one_or_none()
        assert row is None


def test_tax_template_item_rechaza_tax_inexistente_o_inactivo(app, authenticated_client, modulo_admin_activo):
    client = authenticated_client("admin")
    with app.app_context():
        tpl = TaxTemplate(name=f"TPL-{uuid4().hex[:8]}", template_type="selling", is_active=True)
        inactive_tax = Tax(
            name=f"Inactive {uuid4().hex[:8]}",
            rate=10,
            tax_type="percentage",
            applies_to="both",
            is_active=False,
        )
        database.session.add_all([tpl, inactive_tax])
        database.session.commit()
        tpl_id, inactive_tax_id = tpl.id, inactive_tax.id

    resp = client.post(
        f"/settings/tax-templates/{tpl_id}/items",
        data={
            "tax_id": f"missing-{uuid4().hex}",
            "sequence": "10",
            "calculation_base": "net_document",
            "behavior": "additive",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "impuesto activo" in _msg(resp).lower()
    with app.app_context():
        rows = database.session.execute(database.select(TaxTemplateItem).filter_by(tax_template_id=tpl_id)).scalars().all()
        assert rows == []

    resp = client.post(
        f"/settings/tax-templates/{tpl_id}/items",
        data={
            "tax_id": inactive_tax_id,
            "sequence": "10",
            "calculation_base": "net_document",
            "behavior": "additive",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "impuesto activo" in _msg(resp).lower()
    with app.app_context():
        rows = database.session.execute(database.select(TaxTemplateItem).filter_by(tax_template_id=tpl_id)).scalars().all()
        assert rows == []


def test_dimension_value_rechaza_tipo_y_compania_invalidos(app, authenticated_client, modulo_admin_activo):
    client = authenticated_client("admin")
    value = f"VAL-{uuid4().hex[:8]}"

    resp = client.post(
        "/settings/dimensions",
        data={
            "action": "add_value",
            "dimension_type_id": f"missing-{uuid4().hex}",
            "value": value,
            "company": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "tipo de dimensi?n seleccionado no es v?lido" in _msg(resp).lower() or "dimensi" in _msg(resp).lower()
    with app.app_context():
        assert database.session.execute(database.select(DimensionValue).filter_by(value=value)).scalar_one_or_none() is None

    with app.app_context():
        dt = DimensionType(name=f"DT-{uuid4().hex[:8]}", is_active=True)
        database.session.add(dt)
        database.session.commit()
        dt_id = dt.id

    bad_company_value = f"VALCO-{uuid4().hex[:8]}"
    resp = client.post(
        "/settings/dimensions",
        data={
            "action": "add_value",
            "dimension_type_id": dt_id,
            "value": bad_company_value,
            "company": f"ZZ{uuid4().hex[:6]}",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "compa??a seleccionada no es v?lida" in _msg(resp).lower() or "compa" in _msg(resp).lower()
    with app.app_context():
        row = database.session.execute(database.select(DimensionValue).filter_by(value=bad_company_value)).scalar_one_or_none()
        assert row is None
