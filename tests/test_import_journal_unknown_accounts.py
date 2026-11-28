# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1672: el prechequeo de comprobantes rechaza cuentas inexistentes o inactivas."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.imports.adapters.journal_entry import JournalEntryAdapter
from cacao_accounting.database import Accounts, Entity, database

ERROR_CUENTA = "La cuenta 9999 no existe en la compania cacao."


@pytest.fixture(autouse=True)
def cuentas_activas(app, entorno_contable):
    """Los controles positivos usan cuentas operativas sin alterar el fixture."""
    with app.app_context():
        for cuenta in database.session.execute(
            database.select(Accounts).filter(Accounts.code.in_(["1101", "4101"]))
        ).scalars():
            cuenta.active = cuenta.enabled = True
        database.session.flush()
        yield
        database.session.rollback()


def _filas(debito: str, credito: str) -> list[dict[str, str]]:
    return [
        {
            "document_ref": "AS-1672",
            "fecha": "2026-05-15",
            "cuenta": debito,
            "descripcion": "Debe",
            "debito": "100",
            "credito": "0",
            "moneda": "NIO",
        },
        {
            "document_ref": "AS-1672",
            "fecha": "2026-05-15",
            "cuenta": credito,
            "descripcion": "Haber",
            "debito": "0",
            "credito": "100",
            "moneda": "NIO",
        },
    ]


def test_cuenta_inexistente_se_rechaza_en_la_importacion(app, entorno_contable):
    """Un comprobante balanceado con códigos desconocidos no pasa el prechequeo."""
    del entorno_contable
    with app.app_context():
        errores = JournalEntryAdapter().validate_document(_filas("9999", "8888"), {"company_id": "cacao"})

    assert errores == [ERROR_CUENTA]


def test_cuentas_existentes_siguen_aceptandose(app, entorno_contable):
    """Los códigos válidos del catálogo mantienen el flujo sin cambios."""
    del entorno_contable
    with app.app_context():
        errores = JournalEntryAdapter().validate_document(_filas("1101", "4101"), {"company_id": "cacao"})

    assert errores == []


@pytest.mark.parametrize("campo", ["active", "enabled"])
def test_cuenta_desactivada_se_rechaza(app, entorno_contable, campo):
    """Una cuenta de la compañía debe estar activa y habilitada."""
    with app.app_context():
        cuenta = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        anterior = getattr(cuenta, campo)
        try:
            setattr(cuenta, campo, False)
            database.session.flush()
            errores = JournalEntryAdapter().validate_document(_filas("1101", "4101"), {"company_id": "cacao"})
            assert any("activa y habilitada" in error for error in errores)
        finally:
            setattr(cuenta, campo, anterior)
            database.session.rollback()


def _cuenta_ajena() -> Accounts:
    """Crea una cuenta válida de otra compañía para el prechequeo."""
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
        code=f"98{sufijo[:4]}",
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


@pytest.mark.parametrize("forma", ["codigo", "id"])
def test_cuenta_ajena_se_rechaza_en_la_importacion(entorno_contable_aislado, forma):
    """El adaptador no acepta cuentas de otra compañía, ni por código ni por ID."""
    app = entorno_contable_aislado.app
    with app.app_context():
        ajena = _cuenta_ajena()
        valor = ajena.code if forma == "codigo" else ajena.id
        errores = JournalEntryAdapter().validate_document(_filas(valor, "4101"), {"company_id": "cacao"})

    assert len(errores) == 1
    assert "no existe en la compania cacao" in errores[0]
