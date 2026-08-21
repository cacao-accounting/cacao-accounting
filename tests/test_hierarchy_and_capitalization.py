# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Tests unitarios para jerarquías de unidad/proyecto y capitalización automática de proyectos."""

import unittest
from decimal import Decimal
from datetime import date
from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    Unit,
    Project,
    Accounts,
    GLEntry,
    ComprobanteContable,
    ComprobanteContableDetalle,
    AccountingPeriod,
    FiscalYear,
    Entity,
    Book,
    Currency,
    ExchangeRate,
)
from cacao_accounting.database.helpers import check_hierarchy_cycle, update_hierarchy_attributes
from cacao_accounting.contabilidad.project_capitalization_service import ProjectCapitalizationService
from cacao_accounting.contabilidad.posting import cancel_document, PostingError
from cacao_accounting.reportes.services import FinancialReportFilters, get_account_movement_detail


class TestHierarchyAndCapitalization(unittest.TestCase):
    """Pruebas unitarias para Jerarquías y Capitalización de Proyectos."""

    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "SECRET_KEY": "test_key",
            }
        )
        self.app_context = self.app.app_context()
        self.app_context.push()
        database.create_all()

        from cacao_accounting.database import Modules, User

        # Seed initial core data
        self.entity = Entity(
            code="cacao", name="Cacao Corp", company_name="Cacao Corp", tax_id="J0001", currency="NIO", enabled=True
        )
        self.book = Book(
            id="NIO", code="NIO", name="Libro NIO", entity="cacao", currency="NIO", status="activo", is_primary=True
        )
        self.period = AccountingPeriod(
            id="P2026-07",
            name="2026-07",
            start=date(2026, 7, 1),
            end=date(2026, 7, 31),
            entity="cacao",
            fiscal_year_id="2026",
            is_closed=False,
            enabled=True,
        )
        self.fy = FiscalYear(
            id="2026", name="2026", entity="cacao", year_start_date=date(2026, 1, 1), year_end_date=date(2026, 12, 31)
        )
        self.module = Modules(module="accounting", default=True, enabled=True)
        self.user = User(
            id="test_user", user="test_user", name="Test User", password=b"x", classification="admin", active=True
        )

        # Accounts
        self.acc_expense = Accounts(
            id="ACC-EXP-001",
            code="6101",
            name="Gastos de Sueldos",
            entity="cacao",
            classification="Gastos",
            active=True,
            enabled=True,
        )
        self.acc_asset = Accounts(
            id="ACC-AST-001",
            code="1201",
            name="Construcciones en Proceso",
            entity="cacao",
            classification="Activo",
            active=True,
            enabled=True,
        )

        database.session.add_all(
            [self.entity, self.book, self.fy, self.period, self.acc_expense, self.acc_asset, self.module, self.user]
        )
        database.session.commit()

    def tearDown(self):
        database.session.rollback()
        database.drop_all()
        self.app_context.pop()

    def test_business_unit_hierarchy(self):
        """Verifica la asignación, niveles, rutas y prevención de ciclos en Unidades de Negocio."""
        # 1. Crear Jerarquía
        root = Unit(id="U_ROOT", code="BU_ROOT", name="Holding", entity="cacao", enabled=True)
        database.session.add(root)
        database.session.flush()
        update_hierarchy_attributes(root)

        child = Unit(id="U_CHILD", code="BU_CHILD", name="Norte", entity="cacao", enabled=True, parent_id=root.id)
        database.session.add(child)
        database.session.flush()
        update_hierarchy_attributes(child)

        grandchild = Unit(id="U_GCHILD", code="BU_GCHILD", name="Managua", entity="cacao", enabled=True, parent_id=child.id)
        database.session.add(grandchild)
        database.session.flush()
        update_hierarchy_attributes(grandchild)
        database.session.commit()

        # 2. Verificar Atributos
        self.assertEqual(root.level, 0)
        self.assertEqual(root.path, "Holding")
        self.assertEqual(child.level, 1)
        self.assertEqual(child.path, "Holding / Norte")
        self.assertEqual(grandchild.level, 2)
        self.assertEqual(grandchild.path, "Holding / Norte / Managua")

        # 3. Verificar Relaciones/Propiedades
        self.assertIn(child, root.children)
        self.assertEqual(child.parent, root)
        self.assertIn(grandchild, child.descendants)
        self.assertIn(child, grandchild.ancestors)
        self.assertIn(root, grandchild.ancestors)

        # 4. Prevención de Ciclos
        with self.assertRaises(ValueError):
            check_hierarchy_cycle(Unit, root.id, child.id)  # root cannot point to its child (creates a cycle)

        with self.assertRaises(ValueError):
            check_hierarchy_cycle(Unit, child.id, grandchild.id)

        with self.assertRaises(ValueError):
            check_hierarchy_cycle(Unit, child.id, child.id)  # node cannot be its own parent

    def test_project_hierarchy(self):
        """Verifica la asignación, niveles, rutas y prevención de ciclos en Proyectos."""
        root = Project(id="P_ROOT", code="PR_ROOT", name="Planta", entity="cacao", enabled=True)
        database.session.add(root)
        database.session.flush()
        update_hierarchy_attributes(root)

        child = Project(id="P_CHILD", code="PR_CHILD", name="Equipos", entity="cacao", enabled=True, parent_id=root.id)
        database.session.add(child)
        database.session.flush()
        update_hierarchy_attributes(child)
        database.session.commit()

        self.assertEqual(root.level, 0)
        self.assertEqual(child.level, 1)
        self.assertEqual(child.path, "Planta / Equipos")

        with self.assertRaises(ValueError):
            check_hierarchy_cycle(Project, root.id, child.id)

    def test_report_consolidation_with_descendants(self):
        """Verifica que el reporte del libro mayor consolida descendientes si include_descendants está activo."""
        # Configurar unidades jerárquicas
        root_u = Unit(id="U_ROOT", code="BU_ROOT", name="Holding", entity="cacao", enabled=True)
        child_u = Unit(id="U_CHILD", code="BU_CHILD", name="Managua", entity="cacao", enabled=True, parent_id=root_u.id)
        database.session.add_all([root_u, child_u])
        database.session.flush()
        update_hierarchy_attributes(root_u)
        update_hierarchy_attributes(child_u)
        database.session.commit()

        # Crear movimientos contables para ambas unidades
        entry_root = GLEntry(
            posting_date=date(2026, 7, 15),
            company="cacao",
            ledger_id="NIO",
            account_id=self.acc_expense.id,
            account_code=self.acc_expense.code,
            debit=Decimal("1500.00"),
            credit=Decimal("0.00"),
            voucher_type="journal_entry",
            voucher_id="V001",
            unit_code=root_u.code,
            accounting_period_id=self.period.id,
        )
        entry_child = GLEntry(
            posting_date=date(2026, 7, 16),
            company="cacao",
            ledger_id="NIO",
            account_id=self.acc_expense.id,
            account_code=self.acc_expense.code,
            debit=Decimal("3500.00"),
            credit=Decimal("0.00"),
            voucher_type="journal_entry",
            voucher_id="V002",
            unit_code=child_u.code,
            accounting_period_id=self.period.id,
        )
        database.session.add_all([entry_root, entry_child])
        database.session.commit()

        # 1. Consultar sin incluir descendientes (solo nodo raíz)
        filters_no_desc = FinancialReportFilters(
            company="cacao",
            ledger="NIO",
            accounting_period="2026-07",
            unit_code=root_u.code,
            include_descendants=False,
        )
        res_no_desc = get_account_movement_detail(filters_no_desc)
        self.assertEqual(len(res_no_desc.rows), 1)
        self.assertEqual(res_no_desc.rows[0].values["debit"], Decimal("1500.00"))

        # 2. Consultar incluyendo descendientes (raíz + hijos)
        filters_desc = FinancialReportFilters(
            company="cacao",
            ledger="NIO",
            accounting_period="2026-07",
            unit_code=root_u.code,
            include_descendants=True,
        )
        res_desc = get_account_movement_detail(filters_desc)
        # Debería retornar ambas filas, consolidando el valor total de 5000.00
        self.assertEqual(len(res_desc.rows), 2)
        total_debit = sum(row.values["debit"] for row in res_desc.rows)
        self.assertEqual(total_debit, Decimal("5000.00"))

    def test_automatic_project_capitalization(self):
        """Prueba de flujo completo para la Capitalización Automática de Proyectos."""
        eur_book = Book(id="EUR", code="EUR", name="Libro EUR", entity="cacao", currency="EUR", status="activo")
        database.session.add_all(
            [
                Currency(code="NIO", name="Cordoba", decimals=2, active=True),
                Currency(code="USD", name="US Dollar", decimals=2, active=True),
                Currency(code="EUR", name="Euro", decimals=2, active=True),
                eur_book,
                ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36"), date=date(2026, 7, 10)),
                ExchangeRate(origin="USD", destination="EUR", rate=Decimal("0.9"), date=date(2026, 7, 10)),
            ]
        )
        # 1. Crear proyecto capitalizable
        proj = Project(
            id="P_CAP_01",
            code="PR_CAP",
            name="Proyecto Capitalizable",
            entity="cacao",
            enabled=True,
            capitalizable=True,
            capitalization_account_id=self.acc_asset.id,
        )
        database.session.add(proj)
        database.session.commit()

        # 2. Registrar comprobante original con gasto asociado al proyecto
        jv_orig = ComprobanteContable(
            id="JV-ORIG-001",
            entity="cacao",
            book="NIO",
            book_codes='["NIO", "EUR"]',
            status="submitted",
            voucher_type="journal_entry",
            document_no="JV-000100",
        )
        database.session.add(jv_orig)
        database.session.flush()

        gl_orig = GLEntry(
            posting_date=date(2026, 7, 10),
            company="cacao",
            ledger_id="NIO",
            account_id=self.acc_expense.id,
            account_code=self.acc_expense.code,
            debit=Decimal("360.00"),
            credit=Decimal("0.00"),
            debit_in_account_currency=Decimal("10.00"),
            account_currency="USD",
            company_currency="NIO",
            exchange_rate=Decimal("36"),
            voucher_type="journal_entry",
            voucher_id=jv_orig.id,
            document_no=jv_orig.document_no,
            project_code=proj.code,
            accounting_period_id=self.period.id,
        )
        gl_orig_second_line = GLEntry(
            posting_date=date(2026, 7, 10),
            company="cacao",
            ledger_id="NIO",
            account_id=self.acc_expense.id,
            account_code=self.acc_expense.code,
            debit=Decimal("180.00"),
            credit=Decimal("0.00"),
            debit_in_account_currency=Decimal("5.00"),
            account_currency="USD",
            company_currency="NIO",
            exchange_rate=Decimal("36"),
            voucher_type="journal_entry",
            voucher_id=jv_orig.id,
            document_no=jv_orig.document_no,
            project_code=proj.code,
            accounting_period_id=self.period.id,
        )
        database.session.add_all([gl_orig, gl_orig_second_line])
        database.session.commit()

        # 3. Registrar serie de numeración necesaria para el servicio
        from cacao_accounting.database import NamingSeries, Sequence

        seq = Sequence(
            id="SEQ-JV",
            name="Sequence JV",
            current_value=0,
            increment=1,
            padding=5,
            reset_policy="never",
        )
        ns = NamingSeries(
            id="NS-JV",
            name="NS-JV",
            entity_type="journal_entry",
            prefix_template="JV-*YYYY*-",
            is_active=True,
            is_default=True,
        )
        from cacao_accounting.database import SeriesSequenceMap

        ss_map = SeriesSequenceMap(
            naming_series_id=ns.id,
            sequence_id=seq.id,
        )
        database.session.add_all([seq, ns, ss_map])
        database.session.commit()

        # 4. Ejecutar servicio de capitalización automática
        svc = ProjectCapitalizationService()
        success, errors = svc.run_capitalization(company="cacao", period_id=self.period.id, user_id="test_user")

        self.assertEqual(success, 1)
        self.assertEqual(len(errors), 0)

        # 5. Verificar que se creó y contabilizó el comprobante de capitalización
        cap_jv = database.session.execute(
            database.select(ComprobanteContable).filter_by(voucher_type="Capitalización Automática de Proyecto")
        ).scalar_one_or_none()

        self.assertIsNotNone(cap_jv)
        self.assertEqual(cap_jv.capitalization_origin_id, jv_orig.id)
        self.assertEqual(jv_orig.capitalized_by_id, cap_jv.id)

        # Verificar las líneas generadas
        lines = (
            database.session.execute(database.select(ComprobanteContableDetalle).filter_by(transaction_id=cap_jv.id))
            .scalars()
            .all()
        )
        self.assertEqual(len(lines), 4)

        # Debe y Haber deben estar balanceados conservando el mismo proyecto
        debit_lines = [line for line in lines if line.value > 0]
        credit_lines = [line for line in lines if line.value < 0]

        self.assertEqual({line.account for line in debit_lines}, {self.acc_asset.code})
        self.assertEqual({line.project for line in debit_lines}, {proj.code})
        self.assertEqual(sum(line.value for line in debit_lines), Decimal("15.00"))

        self.assertEqual({line.account for line in credit_lines}, {self.acc_expense.code})
        self.assertEqual({line.project for line in credit_lines}, {proj.code})
        self.assertEqual(sum(line.value for line in credit_lines), Decimal("-15.00"))

        capitalization_entries = (
            database.session.execute(database.select(GLEntry).filter_by(voucher_id=cap_jv.id)).scalars().all()
        )
        self.assertEqual(len(capitalization_entries), 8)
        self.assertEqual(
            sum(entry.debit for entry in capitalization_entries if entry.ledger_id == self.book.id), Decimal("540")
        )
        self.assertEqual(
            sum(entry.debit for entry in capitalization_entries if entry.ledger_id == eur_book.id), Decimal("13.5")
        )

        repeated_success, repeated_errors = svc.run_capitalization(
            company="cacao", period_id=self.period.id, user_id="test_user"
        )
        self.assertEqual(repeated_success, 0)
        self.assertEqual(repeated_errors, [])
        self.assertEqual(
            database.session.execute(
                database.select(ComprobanteContable).filter_by(voucher_type="Capitalización Automática de Proyecto")
            )
            .scalars()
            .all(),
            [cap_jv],
        )

        # 6. Intentar anular la transacción original (debe estar bloqueada)
        with self.assertRaises(PostingError):
            cancel_document(jv_orig)

        # 7. Intentar anular el comprobante de capitalización automática (debe estar bloqueado)
        with self.assertRaises(PostingError):
            cancel_document(cap_jv)
