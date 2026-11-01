# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Ciclo de aprobación para tipos documentales sin rama implícita de envío.

Escenario de negocio (issue #1022): la matriz de aprobación configurable
cubre notas de crédito/débito y costos de importación; al conceder el nivel
final el documento debe quedar publicado y contabilizado, no atrapado en
borrador con una solicitud 'Approved'. Los doctypes sin flujo de envío
deben fallar de manera explícita en lugar de silenciarse, y la validación
de negocio de la ruta sigue aplicando bajo aprobación.
"""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database


@pytest.fixture
def motor_aprobaciones():
    """Aplicación en modo cloud con el entorno de negocio de desarrollo."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        from cacao_accounting.database import Modules

        database.session.add_all(
            [
                Modules(module=nombre, default=False, enabled=True)
                for nombre in ("accounting", "cash", "imports", "inventory", "purchases", "sales")
            ]
        )
        database.session.commit()
        from cacao_accounting.auth.roles import crea_roles_predeterminados
        from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
        from cacao_accounting.datos.dev import master_data, periodo_contable

        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        master_data()
        periodo_contable()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _configurar_engine_para(application, doctype: str) -> dict:
    """Habilita el motor de aprobación con una regla de nivel 1 para el doctype."""
    from cacao_accounting.approval_engine import ApprovalEngine
    from cacao_accounting.database import ApprovalMatrix, CacaoConfig, User, database

    database.session.add(CacaoConfig(key="approval_engine_enabled_CACAO", value="True"))
    admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
    database.session.add(
        ApprovalMatrix(
            company_id="CACAO",
            document_type=doctype,
            role_id=None,
            user_id=admin.id,
            min_amount=0,
            max_amount=None,
            approval_level=1,
            enabled=True,
        )
    )
    database.session.commit()
    return {"user": admin, "engine": ApprovalEngine}


def _nota_de_debito_draft(application, *, con_cliente: bool = True):
    """Crea una nota de débito de venta en borrador con una línea de negocio."""
    from cacao_accounting.database import Party, SalesInvoice, SalesInvoiceItem, User, database

    cliente = None
    if con_cliente:
        cliente = database.session.execute(database.select(Party).filter_by(code="C001")).scalar_one()
    confecciono = database.session.execute(database.select(User).filter_by(user="ventas")).scalar_one()
    nota = SalesInvoice(
        company="CACAO",
        customer_id=cliente.id if cliente else None,
        customer_name=cliente.name if cliente else None,
        document_type="sales_debit_note",
        docstatus=0,
        posting_date=date.today(),
        grand_total=10.0,
        total=10.0,
        created_by=confecciono.id,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=1,
    )
    database.session.add(nota)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=nota.id,
            item_code="ART-001",
            item_name="Chocolate 100g",
            qty=1,
            qty_in_base_uom=1,
            uom="UND",
            rate=10,
            amount=10,
        )
    )
    database.session.commit()
    return nota


def _transaccion_bancaria_manual(application):
    """Crea un movimiento bancario manual pendiente sin cuenta asociada."""
    from cacao_accounting.database import Bank, BankAccount, BankTransaction, database

    banco = database.session.execute(database.select(Bank).limit(1)).scalar_one()
    cuenta = BankAccount(
        company="CACAO", bank_id=banco.id, account_name="Cuenta de Pruebas", account_no="PRUEBA-1022", is_active=True
    )
    database.session.add(cuenta)
    database.session.flush()
    transaccion = BankTransaction(
        bank_account_id=cuenta.id,
        identity_key="prueba-1022",
        posting_date=date.today(),
        withdrawal=5.00,
        description="Retiro manual de prueba",
        created_by="ventas",
    )
    database.session.add(transaccion)
    database.session.commit()
    return transaccion


def test_nota_de_debito_aprobada_queda_publicada_y_contabilizada(motor_aprobaciones):
    """El nivel final de aprobación publica y contabiliza la nota de débito."""
    application = motor_aprobaciones
    with application.test_request_context("/"):
        from flask_login import login_user

        from cacao_accounting.database import ApprovalRequest, GLEntry, database

        contexto = _configurar_engine_para(application, "sales_debit_note")
        admin, engine = contexto["user"], contexto["engine"]
        nota = _nota_de_debito_draft(application)

        assert engine.handle_submission(nota, admin, "Nota de débito") is True

        login_user(admin, force=True)
        assert engine.approve(nota, admin, "Concedo el nivel de aprobación") is True
        assert nota.docstatus == 1
        solicitud = (
            database.session.execute(database.select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc()))
            .scalars()
            .first()
        )
        assert solicitud is not None and solicitud.status == "Approved"
        asientos = database.session.execute(database.select(GLEntry).filter_by(voucher_id=nota.id)).scalars().all()
        assert asientos, "La nota de débito aprobada debe quedar contabilizada en el GL"


def test_documento_sin_flujo_de_envio_falla_en_lugar_de_quedar_atrapado(motor_aprobaciones):
    """Un doctype sin rama de envío produce un error explícito y no un 'Approved' silencioso.

    El contrato del motor: si la matriz admite un doctype cuyo envío no tiene
    rama ejecutable, el intento de publicarlo debe fallar de manera audible,
    nunca dejar el documento en borrador con una solicitud 'Approved'.
    """
    application = motor_aprobaciones
    with application.test_request_context("/"):
        from cacao_accounting.approval_engine import ApprovalEngine
        from cacao_accounting.database import User, database

        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        transaccion = _transaccion_bancaria_manual(application)

        with pytest.raises(ValueError):
            ApprovalEngine._execute_submit("bank_transaction", transaccion, admin)


def test_nota_de_debito_sin_tercero_no_se_publica_desde_el_motor(motor_aprobaciones):
    """La validación de negocio de la ruta sigue aplicando bajo aprobación.

    La nota sin cliente puede rechazarse al solicitar o al conceder la
    aprobación, pero en ningún caso queda publicada sin GL ni atrapada
    en una solicitud 'Approved' mientras el documento sigue en borrador.
    """
    application = motor_aprobaciones
    with application.test_request_context("/"):
        from flask_login import login_user

        from cacao_accounting.database import ApprovalRequest, SalesInvoice, database

        contexto = _configurar_engine_para(application, "sales_debit_note")
        admin, engine = contexto["user"], contexto["engine"]
        nota = _nota_de_debito_draft(application, con_cliente=False)
        nota_id = nota.id

        try:
            engine.handle_submission(nota, admin, "Nota sin cliente")
            login_user(admin, force=True)
            engine.approve(nota, admin, "Concedo el nivel")
        except ValueError:
            database.session.rollback()

        publicada = database.session.get(SalesInvoice, nota_id)
        assert publicada is not None
        assert publicada.docstatus == 0
        estados = database.session.execute(database.select(ApprovalRequest)).scalars().all()
        aprobadas_sin_publicar = [s for s in estados if s.status == "Approved"]
        assert aprobadas_sin_publicar == [], "No debe existir una solicitud Approved para un documento sin publicar"
