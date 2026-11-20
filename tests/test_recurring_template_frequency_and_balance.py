# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresiones de balance por línea y frecuencia mensual en plantillas (#1492, #1493)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.contabilidad.recurring_journal_service import (
    RecurringJournalError,
    apply_recurring_template,
    approve_recurring_template,
    create_recurring_template,
)
from cacao_accounting.database import (
    Accounts,
    ComprobanteContable,
    ComprobanteContableDetalle,
    RecurringJournalApplication,
    RecurringJournalItem,
    RecurringJournalTemplate,
    User,
    database,
)


def _template_data(code: str, frequency: str = "monthly") -> dict:
    """Construye el encabezado mínimo aceptado por el servicio."""
    return {
        "code": code,
        "name": "Plantilla QA",
        "company": "cacao",
        "ledger_id": None,
        "books": ["DEFAULT_BOOK"],
        "naming_series_id": None,
        "description": "Plantilla de regresión",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 12, 31),
        "frequency": frequency,
        "currency": None,
    }


def _accounts() -> tuple[str, str, str]:
    """Devuelve dos cuentas reales y el identificador del usuario administrador."""
    cargo = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
    abono = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()
    admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
    return str(cargo.code), str(abono.code), str(admin.id)


def _create_template(code: str, user_id: str, frequency: str = "monthly") -> RecurringJournalTemplate:
    """Crea una plantilla mensual válida de dos líneas."""
    cargo, abono, _ = _accounts()
    return create_recurring_template(
        data=_template_data(code, frequency),
        items=[
            {"account_code": cargo, "debit": 100, "credit": 0},
            {"account_code": abono, "debit": 0, "credit": 100},
        ],
        user_id=user_id,
    )


def _cleanup_templates(codes: list[str]) -> None:
    """Elimina plantillas y comprobantes generados por la prueba."""
    for code in codes:
        plantilla = database.session.execute(
            database.select(RecurringJournalTemplate).filter_by(code=code)
        ).scalar_one_or_none()
        if plantilla is None:
            continue
        aplicaciones = database.session.execute(
            database.select(RecurringJournalApplication).filter_by(template_id=plantilla.id)
        ).scalars()
        for aplicacion in list(aplicaciones):
            if aplicacion.journal_id:
                for linea in database.session.execute(
                    database.select(ComprobanteContableDetalle).filter_by(transaction_id=aplicacion.journal_id)
                ).scalars():
                    database.session.delete(linea)
                comprobante = database.session.get(ComprobanteContable, aplicacion.journal_id)
                if comprobante is not None:
                    database.session.delete(comprobante)
            database.session.delete(aplicacion)
        for linea in database.session.execute(
            database.select(RecurringJournalItem).filter_by(template_id=plantilla.id)
        ).scalars():
            database.session.delete(linea)
        database.session.delete(plantilla)
        database.session.commit()


@pytest.mark.parametrize(
    "amounts",
    [(100, 100), (0, 0)],
)
def test_invalid_line_shape_is_rejected(app, entorno_contable, amounts):
    """Una línea con ambos lados positivos o sin importe no puede aprobarse."""
    code = f"LB{uuid4().hex[:6].upper()}"
    with app.app_context():
        cargo, abono, admin = _accounts()
        with pytest.raises(RecurringJournalError):
            create_recurring_template(
                data=_template_data(code),
                items=[
                    {"account_code": cargo, "debit": amounts[0], "credit": amounts[1]},
                    {"account_code": abono, "debit": 100, "credit": 0},
                ],
                user_id=admin,
            )
        database.session.rollback()
        assert (
            database.session.execute(database.select(RecurringJournalTemplate).filter_by(code=code)).scalar_one_or_none()
            is None
        )


def test_legacy_invalid_template_cannot_be_approved(app, entorno_contable):
    """Una plantilla histórica con ambos lados positivos no se aprueba (#1492)."""
    code = f"LI{uuid4().hex[:6].upper()}"
    try:
        with app.app_context():
            _, _, admin = _accounts()
            plantilla = _create_template(code, admin)
            for item in database.session.execute(
                database.select(RecurringJournalItem).filter_by(template_id=plantilla.id)
            ).scalars():
                item.credit = item.debit
            database.session.commit()

            with pytest.raises(RecurringJournalError, match="positivos"):
                approve_recurring_template(plantilla.id, admin)

            database.session.refresh(plantilla)
            assert plantilla.status == "draft"
    finally:
        with app.app_context():
            _cleanup_templates([code])


def test_legacy_invalid_template_cannot_be_applied(app, entorno_contable):
    """Una plantilla ya aprobada se revalida antes de generar el comprobante (#1492)."""
    code = f"LA{uuid4().hex[:6].upper()}"
    try:
        with app.app_context():
            _, _, admin = _accounts()
            plantilla = _create_template(code, admin)
            approve_recurring_template(plantilla.id, admin)
            primera = (
                database.session.execute(database.select(RecurringJournalItem).filter_by(template_id=plantilla.id))
                .scalars()
                .first()
            )
            primera.credit = primera.debit
            database.session.commit()

            with pytest.raises(RecurringJournalError, match="positivos"):
                apply_recurring_template(
                    plantilla.id,
                    "FY2026",
                    "Mayo 2026",
                    date(2026, 5, 31),
                    admin,
                    company="cacao",
                )
            assert (
                database.session.execute(
                    database.select(RecurringJournalApplication).filter_by(template_id=plantilla.id)
                ).scalar_one_or_none()
                is None
            )
    finally:
        with app.app_context():
            _cleanup_templates([code])


def test_balanced_lines_preserve_the_generated_journal(app, entorno_contable):
    """El comprobante generado conserva débito y crédito de cada línea (#1492)."""
    code = f"AP{uuid4().hex[:6].upper()}"
    try:
        with app.app_context():
            _, _, admin = _accounts()
            plantilla = _create_template(code, admin)
            approve_recurring_template(plantilla.id, admin)
            aplicacion = apply_recurring_template(
                plantilla.id,
                "FY2026",
                "Mayo 2026",
                date(2026, 5, 31),
                admin,
                company="cacao",
            )
            lineas = list(
                database.session.execute(
                    database.select(ComprobanteContableDetalle).filter_by(transaction_id=aplicacion.journal_id)
                ).scalars()
            )
            assert len(lineas) == 2
            assert sum(linea.value for linea in lineas) == Decimal("0")
            assert sorted(linea.value for linea in lineas) == [Decimal("-100"), Decimal("100")]
    finally:
        with app.app_context():
            _cleanup_templates([code])


@pytest.mark.parametrize("frequency", ["weekly", "daily"])
def test_unsupported_frequency_is_rejected_on_creation(app, entorno_contable, frequency):
    """Solo se persisten plantillas mensuales (#1493)."""
    code = f"FR{uuid4().hex[:6].upper()}"
    with app.app_context():
        _, _, admin = _accounts()
        with pytest.raises(RecurringJournalError, match="mensual"):
            _create_template(code, admin, frequency)
        database.session.rollback()
        assert (
            database.session.execute(database.select(RecurringJournalTemplate).filter_by(code=code)).scalar_one_or_none()
            is None
        )


def test_legacy_non_monthly_template_cannot_be_applied(app, entorno_contable):
    """Una fila histórica semanal o diaria no se aplica desde el cierre (#1493)."""
    code = f"LG{uuid4().hex[:6].upper()}"
    try:
        with app.app_context():
            _, _, admin = _accounts()
            plantilla = _create_template(code, admin)
            approve_recurring_template(plantilla.id, admin)
            plantilla.frequency = "weekly"
            database.session.commit()
            with pytest.raises(RecurringJournalError, match="mensual"):
                apply_recurring_template(
                    plantilla.id,
                    "FY2026",
                    "Mayo 2026",
                    date(2026, 5, 31),
                    admin,
                    company="cacao",
                )
            assert (
                database.session.execute(
                    database.select(RecurringJournalApplication).filter_by(template_id=plantilla.id)
                ).scalar_one_or_none()
                is None
            )
    finally:
        with app.app_context():
            _cleanup_templates([code])


def test_two_monthly_templates_apply_on_distinct_dates_in_the_same_period(app, entorno_contable):
    """La idempotencia es por aplicación, no una única plantilla por período (#1493)."""
    first = f"MA{uuid4().hex[:6].upper()}"
    second = f"MB{uuid4().hex[:6].upper()}"
    try:
        with app.app_context():
            _, _, admin = _accounts()
            for code, day in ((first, 5), (second, 20)):
                plantilla = _create_template(code, admin)
                approve_recurring_template(plantilla.id, admin)
                apply_recurring_template(
                    plantilla.id,
                    "FY2026",
                    "Mayo 2026",
                    date(2026, 5, day),
                    admin,
                    company="cacao",
                )
            aplicaciones = database.session.execute(
                database.select(RecurringJournalApplication).where(
                    RecurringJournalApplication.accounting_period == "Mayo 2026"
                )
            ).scalars()
            fechas = {aplicacion.application_date for aplicacion in aplicaciones if aplicacion.template_id}
            assert date(2026, 5, 5) in fechas
            assert date(2026, 5, 20) in fechas
    finally:
        with app.app_context():
            _cleanup_templates([first, second])
