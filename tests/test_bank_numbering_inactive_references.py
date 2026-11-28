# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1982: la numeración bancaria rechaza referencias inactivas."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.bancos.services import _validate_checkbook_default
from cacao_accounting.database import Entity, ExternalCounter, database
from cacao_accounting.document_identifiers import IdentifierConfigurationError


def _contador(company: str = "cacao", activo: bool = True, tipo: str = "checkbook") -> str:
    contador = ExternalCounter(
        company=company,
        name=f"Chequera {uuid4().hex[:5]}",
        last_used=1,
        is_active=activo,
        counter_type=tipo,
    )
    database.session.add(contador)
    database.session.commit()
    return contador.id


def test_chequera_inactiva_se_rechaza(app, entorno_contable):
    """Una chequera desactivada no puede quedar como predeterminada."""
    with app.app_context():
        contador_id = _contador(activo=False)

        with pytest.raises(IdentifierConfigurationError, match="no existe o está inactiva"):
            _validate_checkbook_default(company="cacao", external_counter_id=contador_id)


def test_chequera_activa_de_otra_compania_se_rechaza(app, entorno_contable):
    """La referencia debe pertenecer a la compañía indicada."""
    with app.app_context():
        sufijo = uuid4().hex[:5]
        empresa = f"OT{sufijo}"
        database.session.add(
            Entity(
                code=empresa,
                name="Otra",
                company_name=f"Otra {sufijo} SA",
                tax_id=f"J{sufijo}",
                currency="NIO",
                enabled=True,
            )
        )
        database.session.commit()
        contador_id = _contador(company=empresa)

        with pytest.raises(IdentifierConfigurationError, match="no pertenece"):
            _validate_checkbook_default(company="cacao", external_counter_id=contador_id)


def test_chequera_activa_valida(app, entorno_contable):
    """Una chequera vigente de la compañía se acepta."""
    with app.app_context():
        contador_id = _contador()

        assert _validate_checkbook_default(company="cacao", external_counter_id=contador_id) == contador_id
