# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2176: el cambio de rol de un tercero registra actor y auditoría."""

from __future__ import annotations

import json
from uuid import uuid4

from cacao_accounting.database import AuditTrail, Party, User, database
from cacao_accounting.party_management import toggle_party_supplier_role


def test_toggle_supplier_role_records_actor_and_audit(app, entorno_contable):
    """El actor queda en `modified_by` y en el cambio auditado."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        party = Party(code=f"ROLE-{suffix}", name="Tercero rol", is_customer=True, is_active=True)
        database.session.add(party)
        database.session.commit()
        party_id = party.id
        admin_id = admin.id
        admin_name = admin.name

        toggle_party_supplier_role(party_id, enable=True, user_id=admin_id)
        database.session.commit()

        updated = database.session.get(Party, party_id)
        assert updated.is_supplier is True
        assert updated.modified_by == admin_id

        audit = (
            database.session.execute(
                database.select(AuditTrail)
                .filter_by(document_type="party", document_id=party_id, action="updated")
                .order_by(AuditTrail.timestamp.desc())
            )
            .scalars()
            .first()
        )
        assert audit is not None
        assert audit.actor_user_id == admin_id
        assert audit.actor_name == admin_name
        changes = json.loads(audit.changes_json)
        assert changes["is_supplier"]["before"] is False
        assert changes["is_supplier"]["after"] is True
