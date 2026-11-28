# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2350: sin huella de archivo no se deduplican movimientos sin referencia."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import Bank, BankAccount, BankTransaction, Currency, Entity, database
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter

FECHA = date(2026, 5, 15)


@pytest.fixture
def cuenta(entorno_contable_aislado):
    """Cuenta bancaria aislada para el escenario de importación."""
    application = entorno_contable_aislado.app
    sufijo = uuid4().hex[:6].upper()
    with application.app_context():
        database.session.add_all(
            [
                Currency(code=f"C{sufijo}", name="Moneda", decimals=2, active=True, default=False),
                Entity(
                    code=f"E{sufijo}",
                    name=f"Empresa {sufijo}",
                    company_name=f"Empresa {sufijo} SA",
                    tax_id=f"T{sufijo}",
                    currency=f"C{sufijo}",
                    enabled=True,
                    status="activo",
                ),
            ]
        )
        database.session.flush()
        banco = Bank(name=f"Banco {sufijo}")
        database.session.add(banco)
        database.session.flush()
        cuenta = BankAccount(
            company=f"E{sufijo}",
            bank_id=banco.id,
            account_name=f"Cuenta {sufijo}",
            account_no=f"ACC-{sufijo}",
            currency=f"C{sufijo}",
            is_active=True,
        )
        database.session.add(cuenta)
        database.session.commit()
        return application, cuenta.id


def _fila(account: str, reference: str = "", withdrawal: str = "25") -> dict:
    """Fila de extracto sin referencia opcional."""
    return {
        "bank_account_id": account,
        "posting_date": FECHA,
        "reference_number": reference,
        "description": "Comisión bancaria",
        "deposit": None,
        "withdrawal": Decimal(withdrawal),
    }


def test_sin_huella_y_sin_referencia_falla_de_forma_controlada(cuenta):
    """Dos filas legítimas sin identidad suficiente no se descartan en silencio."""
    application, account = cuenta
    with application.app_context():
        adapter = BankStatementAdapter()
        with pytest.raises(ValueError, match="huella del archivo"):
            adapter.build_document([_fila(account), _fila(account)], {"company_id": None})

        assert (
            database.session.execute(database.select(BankTransaction).filter_by(bank_account_id=account)).scalars().all() == []
        )


def test_sin_huella_con_referencia_conserva_identidad_economica(cuenta):
    """La referencia bancaria sigue siendo identidad suficiente sin huella."""
    application, account = cuenta
    with application.app_context():
        adapter = BankStatementAdapter()
        document = adapter.build_document([_fila(account, reference="REF-1")], {"company_id": None})

        assert document[0]["reference_number"] == "REF-1"
        assert document[0]["import_discriminator"] == ""


def test_con_huella_dos_filas_identicas_se_importan_y_reimportacion_es_idempotente(cuenta):
    """La huella y la posición diferencian cargos repetidos y evitan duplicados."""
    application, account = cuenta
    with application.app_context():
        adapter = BankStatementAdapter()
        contexto = {"company_id": None, "import_fingerprint": "archivo-A"}
        document = adapter.build_document([_fila(account), _fila(account)], contexto)
        assert [tx["import_discriminator"] for tx in document] == ["archivo-A:1", "archivo-A:2"]

        adapter.persist_document(document)
        database.session.commit()
        adapter.persist_document(document)
        database.session.commit()

        filas = database.session.execute(database.select(BankTransaction).filter_by(bank_account_id=account)).scalars().all()
        assert len(filas) == 2
        assert len({fila.identity_key for fila in filas}) == 2


def test_filas_distintas_con_igual_importe_se_conservan_con_huella(cuenta):
    """Dos movimientos del mismo importe y fecha permanecen como evidencia distinta."""
    application, account = cuenta
    with application.app_context():
        adapter = BankStatementAdapter()
        contexto = {"company_id": None, "import_fingerprint": "archivo-B"}
        document = adapter.build_document(
            [_fila(account, withdrawal="25"), _fila(account, withdrawal="30")],
            contexto,
        )

        adapter.persist_document(document)
        database.session.commit()

        filas = database.session.execute(database.select(BankTransaction).filter_by(bank_account_id=account)).scalars().all()
        assert len(filas) == 2
        assert {fila.import_reference for fila in filas} == {"archivo-B:1", "archivo-B:2"}
