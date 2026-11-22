# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1262: política de identidad bancaria sin referencia.

Con referencia bancaria se mantiene la deduplicación económica; sin
referencia, la identidad se apoya en la procedencia de importación (huella
del archivo + posición de fila), de modo que:

- dos cargos legítimos idénticos sin referencia se importan;
- reimportar exactamente el mismo archivo no duplica;
- con referencia el duplicado exacto se sigue rechazando.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import Bank, BankAccount, BankTransaction, Currency, Entity, database
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter

FECHA = date(2026, 5, 15)


def _cuenta(app) -> str:
    suffix = uuid4().hex[:6].upper()
    with app.app_context():
        database.session.add_all(
            [
                Currency(code=f"C{suffix}", name="Moneda", decimals=2, active=True, default=False),
                Entity(
                    code=f"E{suffix}",
                    name=f"Empresa {suffix}",
                    company_name=f"Empresa {suffix} SA",
                    tax_id=f"T{suffix}",
                    currency=f"C{suffix}",
                    enabled=True,
                    status="activo",
                ),
            ]
        )
        database.session.flush()
        bank = Bank(name=f"Banco {suffix}")
        database.session.add(bank)
        database.session.flush()
        account = BankAccount(
            company=f"E{suffix}",
            bank_id=bank.id,
            account_name=f"Cuenta {suffix}",
            account_no=f"ACC-{suffix}",
            currency=f"C{suffix}",
            is_active=True,
        )
        database.session.add(account)
        database.session.commit()
        return account.id


def _row(account: str, reference: str, discriminator: str) -> dict:
    return {
        "bank_account_id": account,
        "company_id": None,
        "posting_date": FECHA,
        "reference_number": reference,
        "description": "Comisión bancaria",
        "deposit": None,
        "withdrawal": Decimal("25"),
        "import_discriminator": discriminator,
    }


def test_dos_cargos_identicos_sin_referencia_se_importan(app, entorno_contable):
    """#1262: dos comisiones idénticas sin referencia no se rechazan."""
    account = _cuenta(app)
    with app.app_context():
        adapter = BankStatementAdapter()
        adapter.persist_document([_row(account, "", "fp1:2"), _row(account, "", "fp1:3")])
        database.session.commit()

        filas = database.session.execute(database.select(BankTransaction).filter_by(bank_account_id=account)).scalars().all()
        assert len(filas) == 2
        assert {f.reference_number for f in filas} == {""}
        # Cada movimiento conserva identidad individual.
        assert len({f.identity_key for f in filas}) == 2


def test_reimportar_el_mismo_archivo_no_duplica(app, entorno_contable):
    """La procedencia (huella + fila) mantiene la idempotencia al reimportar."""
    account = _cuenta(app)
    with app.app_context():
        adapter = BankStatementAdapter()
        fila = _row(account, "", "archivoA:2")
        adapter.persist_document([fila])
        database.session.commit()
        adapter.persist_document([dict(fila)])
        database.session.commit()

        filas = database.session.execute(database.select(BankTransaction).filter_by(bank_account_id=account)).scalars().all()
        assert len(filas) == 1


def test_con_referencia_el_duplicado_exacto_se_rechaza(app, entorno_contable):
    """Con referencia, la deduplicación económica vigente se conserva."""
    account = _cuenta(app)
    with app.app_context():
        adapter = BankStatementAdapter()
        adapter.persist_document([_row(account, "REF-1", "")])
        database.session.commit()

        try:
            adapter.persist_document([_row(account, "REF-1", "")])
        except ValueError as exc:
            assert "ya existe" in str(exc)
        else:
            raise AssertionError("El duplicado con referencia no se rechazó")
        finally:
            database.session.rollback()

        filas = database.session.execute(database.select(BankTransaction).filter_by(bank_account_id=account)).scalars().all()
        assert len(filas) == 1


def test_con_referencia_el_mismo_monto_en_fechas_distintas_se_acepta(app, entorno_contable):
    """Control positivo: la deduplicación con referencia no es demasiado amplia."""
    account = _cuenta(app)
    with app.app_context():
        adapter = BankStatementAdapter()
        adapter.persist_document([_row(account, "REF-A", ""), _row(account, "REF-B", "")])
        database.session.commit()

        filas = database.session.execute(database.select(BankTransaction).filter_by(bank_account_id=account)).scalars().all()
        assert len(filas) == 2
