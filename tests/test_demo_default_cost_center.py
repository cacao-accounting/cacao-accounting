# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2169: MAIN es el único centro de costo predeterminado canónico."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.contabilidad.budget_service import BudgetService
from cacao_accounting.database import CostCenter, Entity, database
from cacao_accounting.datos.dev.data import _make_centros_de_costos


def test_los_centros_demo_no_son_default() -> None:
    """El seed demo no introduce defaults competidores ni agrupadores default."""
    centros = _make_centros_de_costos()
    assert not [centro for centro in centros if centro.default]
    for entidad in ("CACAO", "CAFE", "DULCE"):
        assert any(centro.entity == entidad and not centro.group and centro.active and centro.enabled for centro in centros)


def _sembrar_centros(app, company: str) -> None:
    """Crea MAIN, los centros demo y un agrupador default heredado."""
    with app.app_context():
        database.session.add(
            Entity(
                code=company,
                name=f"Compañía {company}",
                company_name=f"Compañía {company} SA",
                tax_id=f"TAX-{company}",
                currency="NIO",
                enabled=True,
            )
        )
        database.session.flush()
        database.session.add(
            CostCenter(
                entity=company,
                code="MAIN",
                name="Centro principal",
                group=False,
                default=True,
                active=True,
                enabled=True,
            )
        )
        for centro in _make_centros_de_costos():
            if centro.entity == "CACAO":
                centro.entity = company
                database.session.add(centro)
        database.session.add(
            CostCenter(
                entity=company,
                code="GRUPO",
                name="Agrupador heredado",
                group=True,
                default=True,
                active=True,
                enabled=True,
            )
        )
        database.session.commit()


def _limpiar(app, company: str) -> None:
    """Retira la compañía y sus centros al finalizar la prueba."""
    with app.app_context():
        database.session.execute(database.delete(CostCenter).where(CostCenter.entity == company))
        database.session.execute(database.delete(Entity).where(Entity.code == company))
        database.session.commit()


def test_resolver_usa_main_de_forma_repetible(app):
    """La resolución implícita elige MAIN aunque exista un agrupador default."""
    company = f"CC{uuid4().hex[:6].upper()}"
    _sembrar_centros(app, company)
    try:
        with app.app_context():
            servicio = BudgetService()
            assert servicio.resolve_cost_center("", company).code == "MAIN"
            assert servicio.resolve_cost_center("", company).code == "MAIN"
    finally:
        _limpiar(app, company)


def test_resolver_ignora_agrupadores_y_es_determinista_para_legacy(app):
    """Sin MAIN posteable, solo se consideran centros operativos y default."""
    company = f"CC{uuid4().hex[:6].upper()}"
    _sembrar_centros(app, company)
    try:
        with app.app_context():
            principal = database.session.execute(
                database.select(CostCenter).filter_by(entity=company, code="MAIN")
            ).scalar_one()
            principal.active = False
            heredado = database.session.execute(
                database.select(CostCenter).filter_by(entity=company, code="A00000")
            ).scalar_one()
            heredado.default = True
            database.session.commit()
        with app.app_context():
            resultado = BudgetService().resolve_cost_center("", company)
            assert resultado is not None
            assert resultado.code == "A00000"
    finally:
        _limpiar(app, company)
