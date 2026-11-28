# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1642: aprobar la anulación ejecuta el cancel real de la nota de compra.

El dispatcher de aprobaciones reconocía los costos de importación y las notas
de venta, pero no `purchase_credit_note`/`purchase_debit_note`: la solicitud
quedaba aprobada y el documento conservaba `docstatus=1`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import approval_engine
from cacao_accounting.approval_engine import ApprovalEngine, approved_execution
from cacao_accounting.database import Accounts, GLEntry, Party, PurchaseInvoice, User, database
from cacao_accounting.internal_control_service import audit_actor

FECHA = date(2026, 5, 20)


def _nota_aprobada(app, document_type: str) -> str:
    """Crea una nota de compra aprobada con GL balanceado."""
    with app.app_context():
        sufijo = uuid4().hex[:6].upper()
        proveedor = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        nota = PurchaseInvoice(
            company="cacao",
            document_no=f"NOTA-{sufijo}",
            document_type=document_type,
            docstatus=1,
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
            posting_date=FECHA,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(nota)
        database.session.flush()
        cuentas = [
            database.session.execute(database.select(Accounts).filter_by(entity="cacao", code=code)).scalar_one()
            for code in ("5201", "2101")
        ]
        for cuenta, debit, credit in ((cuentas[0], Decimal("100"), Decimal("0")), (cuentas[1], Decimal("0"), Decimal("100"))):
            database.session.add(
                GLEntry(
                    company="cacao",
                    account_id=cuenta.id,
                    account_code=cuenta.code,
                    voucher_type="purchase_invoice",
                    voucher_id=nota.id,
                    posting_date=FECHA,
                    debit=debit,
                    credit=credit,
                    is_cancelled=False,
                )
            )
        database.session.commit()
        return nota.id


@pytest.mark.parametrize("document_type", ["purchase_credit_note", "purchase_debit_note"])
def test_el_dispatcher_reconoce_las_notas_de_compra(document_type):
    """Ambos tipos están en el conjunto de documentos posteados cancelables."""
    assert document_type in approval_engine._POSTED_CANCEL_DOCTYPES


@pytest.mark.parametrize("document_type", ["purchase_credit_note", "purchase_debit_note"])
def test_aprobar_la_anulacion_cancela_la_nota(app, entorno_contable, document_type, monkeypatch):
    """El executor real deja el documento en docstatus=2."""
    del entorno_contable
    nota_id = _nota_aprobada(app, document_type)

    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        nota = database.session.get(PurchaseInvoice, nota_id)
        with audit_actor(admin.id, admin.name), approved_execution(nota, admin.id):
            ApprovalEngine._execute_cancel(
                document_type,
                nota,
                admin,
                reason="Anulación aprobada",
                cancellation_date=FECHA,
            )
        database.session.commit()

    with app.app_context():
        assert database.session.get(PurchaseInvoice, nota_id).docstatus == 2
