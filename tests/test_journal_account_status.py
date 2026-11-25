# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1672: ninguna cuenta inactiva recibe movimientos nuevos.

El importador hace un prechequeo, pero la cuenta puede cambiar de estado entre
la validación y el posteo. Estas regresiones cubren el servicio contable que
crea el borrador y la operación final que genera las líneas GL.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.contabilidad.journal_service import (
    JournalValidationError,
    create_journal_draft,
    submit_journal,
)
from cacao_accounting.contabilidad.posting_service import PostingError
from cacao_accounting.database import (
    Accounts,
    ComprobanteContable,
    ComprobanteContableDetalle,
    Entity,
    GLEntry,
    User,
    database,
)


@pytest.fixture(autouse=True)
def cuentas_operativas(app, entorno_contable):
    """Asegura cuentas hoja activas y restaura su estado al terminar."""
    del entorno_contable
    with app.app_context():
        cuentas = list(
            database.session.execute(
                select(Accounts).where(Accounts.entity == "cacao", Accounts.code.in_(["1101", "4101"]))
            ).scalars()
        )
        estado = [(cuenta.id, cuenta.active, cuenta.enabled) for cuenta in cuentas]
        for cuenta in cuentas:
            cuenta.active = True
            cuenta.enabled = True
        database.session.commit()
    yield
    with app.app_context():
        for cuenta_id, activa, habilitada in estado:
            cuenta = database.session.get(Accounts, cuenta_id)
            if cuenta is not None:
                cuenta.active = activa
                cuenta.enabled = habilitada
        database.session.commit()


def _payload() -> dict[str, object]:
    """Comprobante balanceado en moneda local con las cuentas del escenario."""
    return {
        "company": "cacao",
        "posting_date": "2026-05-15",
        "reference": f"CUENTA-ESTADO-{uuid4().hex[:8]}",
        "transaction_currency": "NIO",
        "base_currency": "NIO",
        "exchange_rate": "1",
        "lines": [
            {"order": 1, "account": "1101", "debit": "100", "credit": ""},
            {"order": 2, "account": "4101", "debit": "", "credit": "100"},
        ],
    }


def _actor_id() -> str:
    """Usuario administrador del entorno contable."""
    return database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()


def _crear_cuenta_ajena() -> Accounts:
    """Crea una compañía y cuenta válidas fuera del alcance del comprobante."""
    sufijo = uuid4().hex[:6]
    entidad = Entity(
        code=f"ot{sufijo}",
        name=f"Otra {sufijo}",
        company_name=f"Otra {sufijo} SA",
        tax_id=f"OT-{sufijo}",
        currency="NIO",
        enabled=True,
    )
    database.session.add(entidad)
    database.session.flush()
    cuenta = Accounts(
        entity=entidad.code,
        code=f"99{sufijo[:4]}",
        name=f"Cuenta ajena {sufijo}",
        classification="asset",
        account_type="cash",
        group=False,
        active=True,
        enabled=True,
    )
    database.session.add(cuenta)
    database.session.flush()
    return cuenta


def _conteos() -> tuple[int, int, int]:
    """Cuenta cabeceras, detalles y asientos GL del entorno aislado."""
    return (
        database.session.execute(select(database.func.count(ComprobanteContable.id))).scalar_one(),
        database.session.execute(select(database.func.count(ComprobanteContableDetalle.id))).scalar_one(),
        database.session.execute(select(database.func.count(GLEntry.id))).scalar_one(),
    )


def test_borrador_rechaza_cuenta_inexistente(app, entorno_contable):
    """Un código ausente del plan de cuentas se rechaza antes de guardar el borrador."""
    del entorno_contable
    with app.app_context():
        payload = _payload()
        payload["lines"][0]["account"] = "NO-SUCH-DEBIT"
        antes = _conteos()
        with pytest.raises(JournalValidationError, match="no existe para la compa"):
            create_journal_draft(payload, user_id=_actor_id(), assign_identifier=False)

        assert _conteos() == antes
        assert (
            database.session.execute(select(ComprobanteContable).where(ComprobanteContable.reference == payload["reference"]))
            .scalars()
            .all()
            == []
        )


def test_posteo_rechaza_cuenta_inexistente_en_linea_legacy(app, entorno_contable):
    """Un borrador heredado con una cuenta inexistente no genera evidencia GL."""
    del entorno_contable
    with app.app_context():
        actor_id = _actor_id()
        journal = create_journal_draft(_payload(), user_id=actor_id, assign_identifier=False)
        journal_id = journal.id
        linea = (
            database.session.execute(
                select(ComprobanteContableDetalle).where(ComprobanteContableDetalle.transaction_id == journal_id)
            )
            .scalars()
            .first()
        )
        linea.account = "NO-SUCH-DEBIT"
        database.session.flush()

        with pytest.raises((JournalValidationError, PostingError), match="no existe para la compa"):
            submit_journal(journal_id, user_id=actor_id)

        assert database.session.execute(select(GLEntry).where(GLEntry.voucher_id == journal_id)).scalars().all() == []
        database.session.rollback()


@pytest.mark.parametrize("caso", ["ajena_codigo", "ajena_id", "inactiva", "deshabilitada"])
def test_posteo_legacy_rechaza_cuenta_ajena_o_no_vigente(entorno_contable_aislado, caso):
    """El posteo revalida la línea forjada, revierte y conserva el borrador."""
    app = entorno_contable_aislado.app
    with app.app_context():
        actor_id = _actor_id()
        journal = create_journal_draft(_payload(), user_id=actor_id, assign_identifier=False)
        journal_id = journal.id
        linea = (
            database.session.execute(
                select(ComprobanteContableDetalle).where(ComprobanteContableDetalle.transaction_id == journal_id)
            )
            .scalars()
            .first()
        )
        cuenta = None
        if caso.startswith("ajena"):
            ajena = _crear_cuenta_ajena()
            linea.account = ajena.code if caso == "ajena_codigo" else ajena.id
        else:
            cuenta = database.session.execute(select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
            setattr(cuenta, "active" if caso == "inactiva" else "enabled", False)
        database.session.flush()

        try:
            with pytest.raises((JournalValidationError, PostingError), match="no existe para la compa|activa, habilitada"):
                submit_journal(journal_id, user_id=actor_id)
            assert database.session.execute(select(GLEntry).where(GLEntry.voucher_id == journal_id)).scalars().all() == []
            assert database.session.get(ComprobanteContable, journal_id) is not None
        finally:
            database.session.rollback()


@pytest.mark.parametrize("field", ["active", "enabled"])
def test_borrador_rechaza_cuenta_inactiva_o_deshabilitada(app, entorno_contable, field):
    """Una cuenta desactivada no puede incorporarse a un borrador nuevo."""
    del entorno_contable
    with app.app_context():
        cuenta = database.session.execute(select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        anterior = getattr(cuenta, field)
        try:
            setattr(cuenta, field, False)
            database.session.flush()
            antes = _conteos()

            with pytest.raises(JournalValidationError, match="activa, habilitada"):
                create_journal_draft(_payload(), user_id=_actor_id(), assign_identifier=False)

            assert _conteos() == antes
        finally:
            setattr(cuenta, field, anterior)
            database.session.rollback()


@pytest.mark.parametrize("forma", ["codigo", "id"])
def test_borrador_rechaza_cuenta_ajena_por_codigo_e_id(entorno_contable_aislado, forma):
    """Una cuenta válida de otra compañía no puede entrar en el borrador."""
    app = entorno_contable_aislado.app
    with app.app_context():
        ajena = _crear_cuenta_ajena()
        payload = _payload()
        payload["lines"][0]["account"] = ajena.code if forma == "codigo" else ajena.id
        antes = _conteos()

        with pytest.raises(JournalValidationError, match="no existe para la compa"):
            create_journal_draft(payload, user_id=_actor_id(), assign_identifier=False)

        assert _conteos() == antes


def test_posteo_revalida_la_cuenta_despues_de_crear_el_borrador(app, entorno_contable):
    """Desactivar la cuenta entre borrador y posteo bloquea el asiento completo."""
    del entorno_contable
    with app.app_context():
        actor_id = _actor_id()
        journal = create_journal_draft(_payload(), user_id=actor_id, assign_identifier=False)
        journal_id = journal.id
        cuenta = database.session.execute(select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        anterior = cuenta.active
        try:
            cuenta.active = False
            database.session.flush()

            with pytest.raises((JournalValidationError, PostingError), match="activa, habilitada"):
                submit_journal(journal_id, user_id=actor_id)
        finally:
            cuenta.active = anterior
            database.session.rollback()

        assert database.session.execute(select(GLEntry).where(GLEntry.voucher_id == journal_id)).scalars().all() == []
