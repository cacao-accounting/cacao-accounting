# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1063: imported account parents resolve to a valid catalog hierarchy."""

from __future__ import annotations

import csv
from uuid import uuid4

import pytest

from cacao_accounting.database import Accounts, Entity, database
from cacao_accounting.imports.adapters.chart_of_accounts import ChartOfAccountsAdapter
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services.import_service import ImportService


@pytest.fixture(name="chart_adapter")
def make_chart_adapter():
    """Create a fresh account catalog adapter for each validation case."""
    return ChartOfAccountsAdapter()


def _account(*, code: str, group: bool, active: bool = True, enabled: bool = True, entity: str = "cacao") -> Accounts:
    """Build one account with explicit hierarchy state."""
    return Accounts(
        entity=entity,
        code=code,
        name=f"Cuenta {code}",
        group=group,
        active=active,
        enabled=enabled,
        classification="asset",
    )


def _row(code: str, parent: str | None = None, group: str = "false") -> dict[str, str | None]:
    """Return one representative catalog row."""
    return {"codigo": code, "nombre": f"Cuenta {code}", "padre": parent, "grupo": group, "clasificacion": "asset"}


def test_empty_document_has_no_parent_to_validate(chart_adapter):
    """An empty group is ignored by document-level parent validation."""
    assert chart_adapter.validate_document([]) == []


def test_existing_parent_must_be_active_and_a_group(app, chart_adapter):
    """Inactive or detail accounts cannot be used as imported parents."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        inactive_code = f"I{suffix}"
        detail_code = f"D{suffix}"
        group_code = f"G{suffix}"
        database.session.add(_account(code=inactive_code, group=True, active=False))
        database.session.add(_account(code=detail_code, group=False))
        database.session.add(_account(code=group_code, group=True))
        database.session.commit()
        try:
            inactive_errors = chart_adapter.validate_document([_row(f"C{suffix}", inactive_code)], {"company_id": "cacao"})
            detail_errors = chart_adapter.validate_document([_row(f"E{suffix}", detail_code)], {"company_id": "cacao"})
            group_errors = chart_adapter.validate_document([_row(f"V{suffix}", group_code)], {"company_id": "cacao"})
            assert inactive_errors == ["La cuenta padre debe estar activa."]
            assert detail_errors == ["La cuenta padre debe ser una cuenta de grupo."]
            assert group_errors == []
        finally:
            Accounts.query.filter(Accounts.code.in_([inactive_code, detail_code, group_code])).delete(
                synchronize_session=False
            )
            database.session.commit()


def test_existing_parent_from_another_company_is_not_resolved(app, chart_adapter):
    """A matching code in another company is not a valid parent reference."""
    suffix = uuid4().hex[:6]
    entity_code = f"x{suffix}"
    parent_code = f"P{suffix}"
    with app.app_context():
        foreign_entity = Entity(
            code=entity_code,
            name=f"Entidad {suffix}",
            company_name=f"Entidad {suffix}",
            tax_id=f"TAX-{suffix}",
            currency="NIO",
            enabled=True,
            status="default",
        )
        database.session.add(foreign_entity)
        database.session.commit()
        try:
            database.session.add(_account(code=parent_code, group=True, entity=entity_code))
            database.session.commit()
            errors = chart_adapter.validate_batch_documents({"1": [_row(f"C{suffix}", parent_code)]}, {"company_id": "cacao"})
            assert errors == ["La cuenta padre indicada no existe para la entidad seleccionada."]
        finally:
            Accounts.query.filter_by(entity=entity_code).delete(synchronize_session=False)
            Entity.query.filter_by(code=entity_code).delete(synchronize_session=False)
            database.session.commit()


def test_parent_declared_later_in_file_is_resolved_before_persist(app, chart_adapter):
    """File order does not prevent a child from resolving its imported group parent."""
    with app.app_context():
        rows = {"1": [_row("CHILD-1063", "PARENT-1063")], "2": [_row("PARENT-1063", group="si")]}
        assert chart_adapter.validate_batch_documents(rows, {"company_id": "cacao"}) == []


def test_account_code_normalization_matches_parent_resolution(app, chart_adapter):
    """Whitespace normalization used for lookup is also applied to persisted codes."""
    with app.app_context():
        child = _row("CHILD-1063", " PARENT-1063 ")
        parent = _row(" PARENT-1063 ", group="si")
        rows = {"1": [child], "2": [parent]}

        assert chart_adapter.validate_batch_documents(rows, {"company_id": "cacao"}) == []
        child_document = chart_adapter.build_document([child], {"company_id": "cacao"})
        parent_document = chart_adapter.build_document([parent], {"company_id": "cacao"})

        assert child_document.parent == parent_document.code == "PARENT-1063"


def test_imported_parent_must_be_group(app, chart_adapter):
    """A detail row in the same file cannot become another account's parent."""
    with app.app_context():
        rows = {"1": [_row("CHILD-1063", "PARENT-1063")], "2": [_row("PARENT-1063")]}
        assert chart_adapter.validate_batch_documents(rows, {"company_id": "cacao"}) == [
            "La cuenta padre debe ser una cuenta de grupo."
        ]


def test_duplicate_imported_parent_is_ambiguous(app, chart_adapter):
    """A parent code repeated in one file cannot resolve to an arbitrary row."""
    with app.app_context():
        rows = {
            "1": [_row("CHILD-1063", "PARENT-1063")],
            "2": [_row("PARENT-1063", group="si")],
            "3": [_row("PARENT-1063", group="si")],
        }
        assert chart_adapter.validate_batch_documents(rows, {"company_id": "cacao"}) == [
            "El código de cuenta padre aparece varias veces en el archivo."
        ]


def test_imported_parent_cycle_is_rejected(app, chart_adapter):
    """A cycle between rows in one file is rejected before any account is saved."""
    with app.app_context():
        rows = {"1": [_row("CYCLE-A-1063", "CYCLE-B-1063", "si")], "2": [_row("CYCLE-B-1063", "CYCLE-A-1063", "si")]}
        assert chart_adapter.validate_batch_documents(rows, {"company_id": "cacao"}) == [
            "La cuenta padre seleccionada genera un ciclo jerarquico."
        ]


def test_cycle_between_imported_and_existing_accounts_is_rejected(app, chart_adapter):
    """A legacy dangling parent cannot be completed into a cycle by an import."""
    suffix = uuid4().hex[:8]
    existing_code = f"X{suffix}"
    imported_code = f"A{suffix}"
    with app.app_context():
        database.session.add(_account(code=existing_code, group=True))
        database.session.flush()
        existing = Accounts.query.filter_by(entity="cacao", code=existing_code).one()
        existing.parent = imported_code
        database.session.commit()
        try:
            rows = {"1": [_row(imported_code, existing_code, "si")]}
            assert chart_adapter.validate_document(rows["1"], {"company_id": "cacao"}) == []
            assert chart_adapter.validate_batch_documents(rows, {"company_id": "cacao"}) == [
                "La cuenta padre seleccionada genera un ciclo jerarquico."
            ]
        finally:
            Accounts.query.filter_by(entity="cacao", code=existing_code).delete(synchronize_session=False)
            database.session.commit()


def test_blank_parent_is_normalized_to_root_account(app, chart_adapter):
    """Whitespace-only parent cells follow the catalog's NULL root convention."""
    with app.app_context():
        document = chart_adapter.build_document([_row("ROOT-1063", "  ")], {"company_id": "cacao"})
        assert document.parent is None


def test_import_validation_rejects_invalid_parent_before_persisting_accounts(app, tmp_path):
    """The active import workflow blocks an invalid hierarchy before execution."""
    suffix = uuid4().hex[:8]
    child_code = f"C{suffix}"
    parent_code = f"P{suffix}"
    source_path = tmp_path / "accounts.csv"
    with source_path.open("w", encoding="utf-8", newline="") as source:
        writer = csv.writer(source)
        writer.writerow(ChartOfAccountsAdapter.columns)
        writer.writerow([child_code, "Cuenta hija", parent_code, "false", "", "asset", ""])
        writer.writerow([parent_code, "Cuenta padre", "", "false", "", "asset", ""])

    with app.app_context():
        batch = ImportBatch(
            company_id="cacao",
            record_type="chart_of_accounts",
            source_format="csv",
            source_filename=source_path.name,
            source_path=str(source_path),
            import_status=1,
        )
        database.session.add(batch)
        database.session.commit()
        try:
            assert ImportService().validate(batch.id)
            assert batch.import_status == 2
            assert ImportBatchError.query.filter_by(batch_id=batch.id, error_type="BUSINESS_RULE").count() == 1
            assert Accounts.query.filter(Accounts.entity == "cacao", Accounts.code.in_([child_code, parent_code])).count() == 0
        finally:
            database.session.delete(batch)
            database.session.commit()


def test_execution_persists_child_before_its_imported_parent(app, tmp_path):
    """A valid out-of-order hierarchy resolves during preflight and persists intact."""
    suffix = uuid4().hex[:8]
    child_code = f"C{suffix}"
    parent_code = f"P{suffix}"
    source_path = tmp_path / "accounts_out_of_order.csv"
    with source_path.open("w", encoding="utf-8", newline="") as source:
        writer = csv.writer(source)
        writer.writerow(ChartOfAccountsAdapter.columns)
        writer.writerow([child_code, "Cuenta hija", f" {parent_code} ", "false", "NIO", "asset", ""])
        writer.writerow([f" {parent_code} ", "Cuenta padre", "", "sí", "NIO", "asset", ""])

    with app.app_context():
        batch = ImportBatch(
            company_id="cacao",
            record_type="chart_of_accounts",
            source_format="csv",
            source_filename=source_path.name,
            source_path=str(source_path),
            import_status=1,
        )
        database.session.add(batch)
        database.session.commit()
        try:
            service = ImportService()
            assert service.validate(batch.id)
            assert batch.import_status == 3
            assert service.execute(batch.id)

            child = Accounts.query.filter_by(entity="cacao", code=child_code).one()
            parent = Accounts.query.filter_by(entity="cacao", code=parent_code).one()
            database.session.refresh(batch)
            assert child.parent == parent.code
            assert parent.group is True
            assert batch.import_status == 5
        finally:
            Accounts.query.filter(Accounts.entity == "cacao", Accounts.code.in_([child_code, parent_code])).delete(
                synchronize_session=False
            )
            database.session.delete(batch)
            database.session.commit()
