# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2319: la adjudicación revalida el proveedor seleccionado.

Entre la cotización de proveedor y la adjudicación el proveedor puede
desactivarse o perder el vínculo con la compañía. El compromiso comercial
no debe crearse en ese estado, aunque la lectura histórica siga disponible.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from cacao_accounting.compras import purchase_sourcing_service
from cacao_accounting.compras.purchase_sourcing_service import (
    PurchaseSourcingError,
    create_purchase_quotation_award,
)
from cacao_accounting.database import (
    CompanyParty,
    Party,
    PurchaseQuotation,
    PurchaseQuotationAward,
    database,
)

FECHA = date(2026, 5, 15)


def _proveedor(*, activo: bool = True, miembro: bool = True) -> str:
    """Crea un proveedor con la vigencia y el vínculo indicados."""
    party = Party(code="PRV-2319", name="Proveedor 2319", is_supplier=True, is_active=activo)
    database.session.add(party)
    database.session.flush()
    if miembro:
        database.session.add(CompanyParty(company="cacao", party_id=party.id, is_active=True))
    database.session.commit()
    return str(party.id)


def _rfq() -> PurchaseQuotation:
    """Crea una RFQ aprobada sobre la compañía de prueba."""
    rfq = PurchaseQuotation(
        company="cacao",
        posting_date=FECHA,
        docstatus=1,
        document_no="RFQ-2319",
        transaction_currency="NIO",
        base_currency="NIO",
    )
    database.session.add(rfq)
    database.session.commit()
    return rfq


def _preparar_adjudicacion(app, monkeypatch, *, activo: bool = True, miembro: bool = True):
    """Devuelve RFQ, selección y oferta con el proveedor en el estado pedido."""
    provider_id = _proveedor(activo=activo, miembro=miembro)
    rfq = _rfq()
    offer = SimpleNamespace(id="offer-2319", supplier_id=provider_id)
    monkeypatch.setattr(
        purchase_sourcing_service,
        "validate_award_request",
        lambda *_args, **_kwargs: ([], [offer], set()),
    )
    return rfq, {"line-2319": offer.id}, provider_id


def test_adjudicacion_rechaza_proveedor_desactivado(entorno_contable_aislado, monkeypatch):
    """Un proveedor desactivado después de cotizar no genera compromiso."""
    app = entorno_contable_aislado.app
    with app.app_context():
        rfq, selections, _provider_id = _preparar_adjudicacion(app, monkeypatch, activo=False)

        with pytest.raises(PurchaseSourcingError, match="no está habilitado como proveedor"):
            create_purchase_quotation_award(rfq, selections, None)
        database.session.rollback()

        assert database.session.execute(database.select(PurchaseQuotationAward)).scalars().all() == []


def test_adjudicacion_rechaza_vinculo_ausente(entorno_contable_aislado, monkeypatch):
    """Un proveedor sin CompanyParty no puede recibir la adjudicación."""
    app = entorno_contable_aislado.app
    with app.app_context():
        rfq, selections, _provider_id = _preparar_adjudicacion(app, monkeypatch, miembro=False)

        with pytest.raises(PurchaseSourcingError, match="no está habilitado para la compañía"):
            create_purchase_quotation_award(rfq, selections, None)
        database.session.rollback()

        assert database.session.execute(database.select(PurchaseQuotationAward)).scalars().all() == []


def test_adjudicacion_rechaza_vinculo_inactivo(entorno_contable_aislado, monkeypatch):
    """Un vínculo inactivo tampoco autoriza el compromiso."""
    app = entorno_contable_aislado.app
    with app.app_context():
        rfq, selections, provider_id = _preparar_adjudicacion(app, monkeypatch)
        vinculo = database.session.execute(
            database.select(CompanyParty).filter_by(party_id=provider_id, company="cacao")
        ).scalar_one()
        vinculo.is_active = False
        database.session.commit()

        with pytest.raises(PurchaseSourcingError, match="no está habilitado para la compañía"):
            create_purchase_quotation_award(rfq, selections, None)
        database.session.rollback()

        assert database.session.execute(database.select(PurchaseQuotationAward)).scalars().all() == []


def test_adjudicacion_con_proveedor_vigente_crea_el_compromiso(entorno_contable_aislado, monkeypatch):
    """Control positivo: el mismo flujo con proveedor vigente adjudica."""
    app = entorno_contable_aislado.app
    with app.app_context():
        rfq, selections, _provider_id = _preparar_adjudicacion(app, monkeypatch)

        award = create_purchase_quotation_award(rfq, selections, None)
        database.session.commit()

        assert award.purchase_quotation_id == rfq.id
        rows = (
            database.session.execute(database.select(PurchaseQuotationAward).filter_by(purchase_quotation_id=rfq.id))
            .scalars()
            .all()
        )
        assert len(rows) == 1
