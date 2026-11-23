# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1823: la aprobación revalida que el proveedor siga vigente."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.compras.services import _validated_purchase_supplier
from cacao_accounting.database import CompanyParty, Entity, Party, database


def _proveedor(company: str, activo: bool = True, miembro: bool = True) -> str:
    sufijo = uuid4().hex[:5]
    proveedor = Party(code=f"P{sufijo}", name="Proveedor", is_supplier=True, is_active=activo)
    database.session.add(proveedor)
    database.session.flush()
    if miembro:
        database.session.add(CompanyParty(company=company, party_id=proveedor.id, is_active=True))
    database.session.commit()
    return proveedor.id


def _empresa() -> str:
    sufijo = uuid4().hex[:5]
    codigo = f"S{sufijo}"
    database.session.add(
        Entity(
            code=codigo,
            name="Sociedad",
            company_name=f"Sociedad {sufijo}",
            tax_id=f"J{sufijo}",
            currency="NIO",
            enabled=True,
        )
    )
    database.session.commit()
    return codigo


def test_proveedor_desactivado_no_aprueba(app, entorno_contable):
    """Si el proveedor se desactiva mientras espera aprobación, se rechaza."""
    with app.app_context():
        empresa = _empresa()
        proveedor_id = _proveedor(empresa)

        assert _validated_purchase_supplier(proveedor_id, empresa) is not None

        database.session.get(Party, proveedor_id).is_active = False
        database.session.commit()

        with pytest.raises(ValueError, match="no está habilitado como proveedor"):
            _validated_purchase_supplier(proveedor_id, empresa)


def test_membresia_revocada_no_aprueba(app, entorno_contable):
    """Revocar el vínculo con la compañía también bloquea la aprobación."""
    with app.app_context():
        empresa = _empresa()
        proveedor_id = _proveedor(empresa)

        vinculo = database.session.execute(database.select(CompanyParty).filter_by(party_id=proveedor_id)).scalar_one()
        vinculo.is_active = False
        database.session.commit()

        with pytest.raises(ValueError, match="no está habilitado para la compañía"):
            _validated_purchase_supplier(proveedor_id, empresa)


def test_la_aprobacion_invoca_la_validacion_de_proveedor():
    """El motor de aprobaciones revalida el proveedor de una orden de compra."""
    from pathlib import Path

    fuente = (
        Path(__file__).resolve().parents[1] / "cacao_accounting" / "approval_engine.py"
    ).read_text(encoding="utf-8")

    assert 'if doctype == "purchase_order":' in fuente
    assert "_validated_purchase_supplier(" in fuente
