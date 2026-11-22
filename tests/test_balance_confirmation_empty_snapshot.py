# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2109: el detalle de confirmación se renderiza con snapshot ausente/vacío.

`_verified_snapshot_for_detail()` devuelve `{}` cuando el snapshot es NULL,
vacío o tiene hash inválido; la ruta normaliza `items`/`totals` para que la
plantilla no interprete `snapshot["items"]` como el método `dict.items` ni
produzca HTTP 500.
"""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad import balance_confirmation_bp
from cacao_accounting.database import BalanceConfirmation, Currency, Entity, Party, User, database


@pytest.fixture
def confirmation_snapshot_scenario(tmp_path):
    """Compañía, admin y confirmación sin snapshot, en base de archivo."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'snapshot.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
            "SECRET_KEY": "snapshot-test",
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Admin",
                    password=b"x",
                    classification="admin",
                    active=True,
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        party = Party(code="CLI-2109", name="Cliente", is_customer=True, is_active=True)
        database.session.add(party)
        database.session.flush()
        confirmation = BalanceConfirmation(
            company="cacao",
            party_type="customer",
            party_id=party.id,
            cutoff_date=date(2026, 5, 15),
            status="draft",
            snapshot_json=None,
            snapshot_hash=None,
        )
        database.session.add(confirmation)
        database.session.commit()
        cid = confirmation.id
    yield app, cid
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_snapshot_ausente_devuelve_dict_vacio(confirmation_snapshot_scenario):
    """Sin snapshot, el helper devuelve `{}` y marca inválido, sin excepción."""
    application, cid = confirmation_snapshot_scenario
    with application.app_context():
        confirmation = database.session.get(BalanceConfirmation, cid)
        snapshot, valid = balance_confirmation_bp._verified_snapshot_for_detail(confirmation)
        assert snapshot == {}
        assert valid is False


def test_ruta_normaliza_items_y_totals_antes_de_renderizar():
    """La vista normaliza `items`/`totals` para no iterar `dict.items` (#2109)."""
    import inspect

    source = inspect.getsource(balance_confirmation_bp.ver_confirmacion)
    assert 'isinstance(snapshot.get("items"), list)' in source
    assert 'snapshot["items"] = []' in source
    assert 'isinstance(snapshot.get("totals"), dict)' in source
    assert 'snapshot["totals"] = {}' in source
