# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""CSRF-protected forms keep every import wizard action usable in Cloud."""

from __future__ import annotations

import re

import pytest

from cacao_accounting.database import Entity, Modules, NamingSeries, database
from cacao_accounting.imports.models import ImportBatch


@pytest.fixture
def import_csrf_pages(app, entorno_contable, authenticated_client, tmp_path):
    """Enable real CSRF and seed one batch for each state-specific form."""
    previous_csrf = app.config["WTF_CSRF_ENABLED"]
    previous_desktop = app.config.get("MODO_ESCRITORIO")
    app.config.update(WTF_CSRF_ENABLED=True, MODO_ESCRITORIO=False)
    with app.app_context():
        imports_module = database.session.execute(database.select(Modules).filter_by(module="imports")).scalar_one_or_none()
        if imports_module is None:
            imports_module = Modules(module="imports", default=False, enabled=True)
            database.session.add(imports_module)
        imports_module.enabled = True
        source_path = tmp_path / "customer.csv"
        source_path.write_text("name,email\nCliente,cliente@example.test\n", encoding="utf-8")
        batches = {}
        for status in (0, 1, 3, 4):
            batch = ImportBatch(
                company_id="cacao",
                record_type="customer",
                import_status=status,
                source_format="csv" if status else None,
                source_filename="customer.csv" if status else None,
                source_path=str(source_path) if status else None,
            )
            database.session.add(batch)
            database.session.flush()
            batches[status] = batch.id
        database.session.commit()
    client = authenticated_client("admin")
    yield app, client, batches
    with app.app_context():
        database.session.execute(database.delete(ImportBatch).where(ImportBatch.id.in_(batches.values())))
        database.session.commit()
    app.config["WTF_CSRF_ENABLED"] = previous_csrf
    app.config["MODO_ESCRITORIO"] = previous_desktop


def _form_token(html: str) -> str:
    """Return the token embedded in a rendered POST form."""
    form = re.search(r"<form\b[^>]*>(.*?)</form>", html, flags=re.DOTALL)
    assert form is not None
    token = re.search(r'name="csrf_token"\s+value="([^"]+)"', form.group(1))
    assert token is not None
    return token.group(1)


def test_new_import_form_rejects_missing_token_and_accepts_valid_token(import_csrf_pages):
    """The creation form can submit under CSRFProtect without disabling CSRF."""
    _app, client, _batches = import_csrf_pages
    page = client.get("/imports/new")
    assert page.status_code == 200
    token = _form_token(page.get_data(as_text=True))

    rejected = client.post("/imports/new", data={"company_id": "cacao", "record_type": "customer"})
    assert rejected.status_code == 400

    accepted = client.post(
        "/imports/new",
        data={"company_id": "cacao", "record_type": "customer", "csrf_token": token},
    )
    assert accepted.status_code == 302
    with _app.app_context():
        created_batches = (
            database.session.execute(database.select(ImportBatch).filter_by(record_type="customer")).scalars().all()
        )
        assert len(created_batches) >= 5


@pytest.mark.parametrize(
    ("record_type", "series_type", "series_company", "expected_error"),
    [
        ("purchase_order", "sales_invoice", "cacao", "no coincide con el tipo"),
        ("purchase_order", "purchase_order", "alpha", "no pertenece a la compañía"),
    ],
)
def test_new_import_rejects_series_for_other_type_or_company(
    import_csrf_pages, record_type, series_type, series_company, expected_error
):
    """Creation rejects a naming series whose type or company differs from the batch."""
    app, client, _batches = import_csrf_pages
    page = client.get("/imports/new")
    token = _form_token(page.get_data(as_text=True))
    with app.app_context():
        if (
            series_company == "alpha"
            and not database.session.execute(database.select(Entity).filter_by(code="alpha")).scalar_one_or_none()
        ):
            database.session.add(
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J-ALPHA",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                )
            )
            database.session.flush()
        series = NamingSeries(
            name=f"SER-{series_type}-{series_company}",
            entity_type=series_type,
            company=series_company,
            prefix_template="TEST-",
            is_active=True,
            is_default=False,
        )
        database.session.add(series)
        database.session.commit()
        series_id = series.id
        count_before = database.session.query(ImportBatch).count()

    response = client.post(
        "/imports/new",
        data={
            "company_id": "cacao",
            "record_type": record_type,
            "sequence_id": series_id,
            "csrf_token": token,
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert expected_error in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.query(ImportBatch).count() == count_before


def test_new_import_persists_series_matching_type_and_company(import_csrf_pages):
    """A valid company-specific series remains attached to the new batch."""
    app, client, _batches = import_csrf_pages
    page = client.get("/imports/new")
    token = _form_token(page.get_data(as_text=True))
    with app.app_context():
        series = NamingSeries(
            name="SER-PO-CACAO",
            entity_type="purchase_order",
            company="cacao",
            prefix_template="PO-",
            is_active=True,
            is_default=False,
        )
        database.session.add(series)
        database.session.commit()
        series_id = series.id

    response = client.post(
        "/imports/new",
        data={
            "company_id": "cacao",
            "record_type": "purchase_order",
            "sequence_id": series_id,
            "csrf_token": token,
        },
    )

    assert response.status_code == 302
    with app.app_context():
        batch = database.session.execute(database.select(ImportBatch).filter_by(sequence_id=series_id)).scalar_one()
        assert batch.company_id == "cacao"
        assert batch.record_type == "purchase_order"


@pytest.mark.parametrize(
    ("status", "action"),
    [(0, "upload"), (1, "validate"), (3, "execute"), (4, "cancel")],
)
def test_import_detail_forms_carry_csrf_and_reach_their_route(import_csrf_pages, status, action):
    """Upload, validation, execution and cancellation forms submit their token."""
    _app, client, batches = import_csrf_pages
    batch_id = batches[status]
    page = client.get(f"/imports/{batch_id}")
    assert page.status_code == 200
    token = _form_token(page.get_data(as_text=True))
    url = f"/imports/{batch_id}/{action}"

    rejected = client.post(url)
    assert rejected.status_code == 400

    accepted = client.post(url, data={"csrf_token": token})
    assert accepted.status_code != 400
