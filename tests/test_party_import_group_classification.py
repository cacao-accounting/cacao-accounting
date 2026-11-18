# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1048: la importación de terceros conserva grupo y clasificación.

`grupo` se resuelve por nombre exacto de un PartyGroup activo y compatible;
`clasificacion` corresponde a Party.person_type (natural/juridical). Los
valores inválidos se rechazan; nunca se descartan en silencio.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Party, PartyGroup, database
from cacao_accounting.imports.adapters.customer import CustomerAdapter
from cacao_accounting.imports.adapters.vendor import VendorAdapter
from cacao_accounting.party_management import find_party_group_by_name


@pytest.fixture
def party_import_scenario():
    """Create active and inactive groups for both roles."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        groups = {
            "customer": PartyGroup(group_type="customer", name="Minoristas", is_active=True, description=suffix),
            "customer_inactive": PartyGroup(
                group_type="customer", name="Clientes inactivos", is_active=False, description=suffix
            ),
            "supplier": PartyGroup(group_type="supplier", name="Mayoristas", is_active=True, description=suffix),
        }
        database.session.add_all(groups.values())
        database.session.commit()
        ids = {key: group.id for key, group in groups.items()}

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _row(name: str, **extra) -> dict:
    """Build one party import row."""
    return {"nombre": name, **extra}


def test_customer_import_maps_group_and_person_type(party_import_scenario):
    """The valid values are persisted on the Party."""
    app, ids = party_import_scenario
    adapter = CustomerAdapter()

    with app.app_context():
        row = _row("Cliente A", grupo="Minoristas", clasificacion="Natural")
        assert adapter.validate_row(row) == []
        document = adapter.build_document([row], {"company_id": None})
        party = document["party"]
        assert party.party_group_id == ids["customer"]
        assert party.person_type == "natural"
        adapter.persist_document(document)
        database.session.commit()
        persisted = database.session.get(Party, party.id)
        assert persisted.party_group_id == ids["customer"]
        assert persisted.person_type == "natural"


def test_vendor_import_maps_its_group_and_juridical_person(party_import_scenario):
    """The supplier adapter uses the supplier group."""
    app, ids = party_import_scenario
    adapter = VendorAdapter()

    with app.app_context():
        row = _row("Proveedor A", grupo="Mayoristas", clasificacion="juridical")
        assert adapter.validate_row(row) == []
        document = adapter.build_document([row], {"company_id": None})
        assert document["party"].party_group_id == ids["supplier"]
        assert document["party"].person_type == "juridical"


def test_group_name_is_exact_and_must_be_active_and_compatible(party_import_scenario):
    """Case, inactivity and role mismatches are rejected."""
    app, ids = party_import_scenario
    customer = CustomerAdapter()

    with app.app_context():
        assert find_party_group_by_name("Minoristas", "customer").id == ids["customer"]
        assert find_party_group_by_name("minoristas", "customer") is None
        assert find_party_group_by_name("Mayoristas", "customer") is None

        for group_name in ("NoExiste", "Clientes inactivos", "Mayoristas"):
            errors = customer.validate_row(_row("Cliente", grupo=group_name))
            assert any("grupo" in error for error in errors), group_name
            with pytest.raises(ValueError):
                customer.build_document([_row("Cliente", grupo=group_name)], {"company_id": None})


@pytest.mark.parametrize("value", ["empresa", "fisica", "JURIDICA"])
def test_invalid_classification_is_rejected(party_import_scenario, value):
    """Only the canonical natural/juridical values are accepted."""
    app, _ids = party_import_scenario
    adapter = CustomerAdapter()

    with app.app_context():
        errors = adapter.validate_row(_row("Cliente", clasificacion=value))
        assert any("clasificación" in error for error in errors)
        with pytest.raises(ValueError):
            adapter.build_document([_row("Cliente", clasificacion=value)], {"company_id": None})
