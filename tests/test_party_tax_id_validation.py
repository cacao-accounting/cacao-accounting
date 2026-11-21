# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2130: el alta manual de terceros no duplica la identificación fiscal."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Party, database
from cacao_accounting.party_management import validated_party_tax_id


def test_rechaza_identificacion_de_otro_tercero(app, entorno_contable):
    """Un `tax_id` ya usado por otro tercero se rechaza antes de crear."""
    sufijo = uuid4().hex[:8]
    with app.app_context():
        existente = Party(code=f"TAX-{sufijo}", name="Existente", tax_id=f"J-{sufijo}")
        database.session.add(existente)
        database.session.commit()
        existente_id = existente.id
        tax_id = existente.tax_id

        with pytest.raises(ValueError, match="identificador fiscal"):
            validated_party_tax_id({"tax_id": tax_id})

        assert validated_party_tax_id({"tax_id": tax_id}, exclude_party_id=existente_id) == tax_id
        assert validated_party_tax_id({"tax_id": ""}) is None
