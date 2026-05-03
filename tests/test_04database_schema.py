# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Pruebas del esquema de base de datos y el framework de series e identificadores."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# ---------------------------------------------------------------------------------------
import unittest
from datetime import date

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
import pytest

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting import create_app
from cacao_accounting.config import configuracion


# -------------------------------------------------------------------------------------
# Fixtures y configuracion
# -------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    """Instancia de aplicacion Flask con base de datos en memoria."""
    _app = create_app(configuracion)
    _app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    _app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    return _app


@pytest.fixture(scope="module")
def app_ctx(app):
    """Contexto de aplicacion activo para el modulo de tests."""
    with app.app_context():
        from cacao_accounting.database import database

        database.create_all()
        yield app


# -------------------------------------------------------------------------------------
# Tests: Esquema de base de datos — creacion de tablas
# -------------------------------------------------------------------------------------
class TestSchemaTableCreation(unittest.TestCase):
    """Verifica que todas las tablas del esquema se crean correctamente en SQLite."""

    def setUp(self):
        """Configura la aplicacion y crea el esquema en memoria."""
        self.app = create_app(configuracion)
        self.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.ctx = self.app.app_context()
        self.ctx.push()
        from cacao_accounting.database import database
        from sqlalchemy import inspect

        database.create_all()
        self.inspector = inspect(database.engine)
        self.tables = set(self.inspector.get_table_names())

    def tearDown(self):
        self.ctx.pop()

    # Core contable
    def test_fiscal_year_table_exists(self):
        self.assertIn("fiscal_year", self.tables)

    def test_accounting_period_table_exists(self):
        self.assertIn("accounting_period", self.tables)

    def test_accounts_table_exists(self):
        self.assertIn("accounts", self.tables)

    def test_book_table_exists(self):
        self.assertIn("book", self.tables)

    def test_gl_entry_table_exists(self):
        self.assertIn("gl_entry", self.tables)

    def test_cost_center_table_exists(self):
        self.assertIn("cost_center", self.tables)

    def test_project_table_exists(self):
        self.assertIn("project", self.tables)

    # Company
    def test_entity_table_exists(self):
        self.assertIn("entity", self.tables)

    def test_unit_table_exists(self):
        self.assertIn("unit", self.tables)

    # Currency
    def test_currency_table_exists(self):
        self.assertIn("currency", self.tables)

    def test_exchange_rate_table_exists(self):
        self.assertIn("exchange_rate", self.tables)

    # Auth
    def test_user_table_exists(self):
        self.assertIn("user", self.tables)

    def test_roles_table_exists(self):
        self.assertIn("roles", self.tables)

    def test_roles_access_table_exists(self):
        self.assertIn("roles_access", self.tables)

    def test_roles_user_table_exists(self):
        self.assertIn("roles_user", self.tables)

    def test_modules_table_exists(self):
        self.assertIn("modules", self.tables)

    # Series
    def test_naming_series_table_exists(self):
        self.assertIn("naming_series", self.tables)

    def test_sequence_table_exists(self):
        self.assertIn("sequence", self.tables)

    def test_series_sequence_map_table_exists(self):
        self.assertIn("series_sequence_map", self.tables)

    def test_generated_identifier_log_table_exists(self):
        self.assertIn("generated_identifier_log", self.tables)

    # Party
    def test_party_table_exists(self):
        self.assertIn("party", self.tables)

    def test_contact_table_exists(self):
        self.assertIn("contact", self.tables)

    def test_address_table_exists(self):
        self.assertIn("address", self.tables)

    def test_party_contact_table_exists(self):
        self.assertIn("party_contact", self.tables)

    def test_party_address_table_exists(self):
        self.assertIn("party_address", self.tables)

    def test_company_party_table_exists(self):
        self.assertIn("company_party", self.tables)

    # Inventory
    def test_uom_table_exists(self):
        self.assertIn("uom", self.tables)

    def test_item_table_exists(self):
        self.assertIn("item", self.tables)

    def test_item_uom_conversion_table_exists(self):
        self.assertIn("item_uom_conversion", self.tables)

    def test_warehouse_table_exists(self):
        self.assertIn("warehouse", self.tables)

    def test_batch_table_exists(self):
        self.assertIn("batch", self.tables)

    def test_serial_number_table_exists(self):
        self.assertIn("serial_number", self.tables)

    def test_stock_entry_table_exists(self):
        self.assertIn("stock_entry", self.tables)

    def test_stock_entry_item_table_exists(self):
        self.assertIn("stock_entry_item", self.tables)

    def test_stock_ledger_entry_table_exists(self):
        self.assertIn("stock_ledger_entry", self.tables)

    def test_stock_bin_table_exists(self):
        self.assertIn("stock_bin", self.tables)

    def test_stock_valuation_layer_table_exists(self):
        self.assertIn("stock_valuation_layer", self.tables)

    # Purchasing
    def test_purchase_order_table_exists(self):
        self.assertIn("purchase_order", self.tables)

    def test_purchase_order_item_table_exists(self):
        self.assertIn("purchase_order_item", self.tables)

    def test_purchase_receipt_table_exists(self):
        self.assertIn("purchase_receipt", self.tables)

    def test_purchase_receipt_item_table_exists(self):
        self.assertIn("purchase_receipt_item", self.tables)

    def test_purchase_invoice_table_exists(self):
        self.assertIn("purchase_invoice", self.tables)

    def test_purchase_invoice_item_table_exists(self):
        self.assertIn("purchase_invoice_item", self.tables)

    # Sales
    def test_sales_order_table_exists(self):
        self.assertIn("sales_order", self.tables)

    def test_sales_order_item_table_exists(self):
        self.assertIn("sales_order_item", self.tables)

    def test_delivery_note_table_exists(self):
        self.assertIn("delivery_note", self.tables)

    def test_delivery_note_item_table_exists(self):
        self.assertIn("delivery_note_item", self.tables)

    def test_sales_invoice_table_exists(self):
        self.assertIn("sales_invoice", self.tables)

    def test_sales_invoice_item_table_exists(self):
        self.assertIn("sales_invoice_item", self.tables)

    # Banking
    def test_bank_table_exists(self):
        self.assertIn("bank", self.tables)

    def test_bank_account_table_exists(self):
        self.assertIn("bank_account", self.tables)

    def test_payment_entry_table_exists(self):
        self.assertIn("payment_entry", self.tables)

    def test_payment_reference_table_exists(self):
        self.assertIn("payment_reference", self.tables)

    def test_bank_transaction_table_exists(self):
        self.assertIn("bank_transaction", self.tables)

    # Account mapping
    def test_item_account_table_exists(self):
        self.assertIn("item_account", self.tables)

    def test_party_account_table_exists(self):
        self.assertIn("party_account", self.tables)

    def test_company_default_account_table_exists(self):
        self.assertIn("company_default_account", self.tables)

    # Tax & Pricing
    def test_tax_table_exists(self):
        self.assertIn("tax", self.tables)

    def test_tax_template_table_exists(self):
        self.assertIn("tax_template", self.tables)

    def test_tax_template_item_table_exists(self):
        self.assertIn("tax_template_item", self.tables)

    def test_price_list_table_exists(self):
        self.assertIn("price_list", self.tables)

    def test_item_price_table_exists(self):
        self.assertIn("item_price", self.tables)

    # Reconciliation & GR/IR
    def test_reconciliation_table_exists(self):
        self.assertIn("reconciliation", self.tables)

    def test_reconciliation_item_table_exists(self):
        self.assertIn("reconciliation_item", self.tables)

    def test_gr_ir_reconciliation_table_exists(self):
        self.assertIn("gr_ir_reconciliation", self.tables)

    # Multi-Ledger
    def test_ledger_mapping_rule_table_exists(self):
        self.assertIn("ledger_mapping_rule", self.tables)

    # Revaluation & Period Close
    def test_exchange_revaluation_table_exists(self):
        self.assertIn("exchange_revaluation", self.tables)

    def test_exchange_revaluation_item_table_exists(self):
        self.assertIn("exchange_revaluation_item", self.tables)

    def test_period_close_run_table_exists(self):
        self.assertIn("period_close_run", self.tables)

    def test_period_close_check_table_exists(self):
        self.assertIn("period_close_check", self.tables)

    # Dimensions
    def test_dimension_type_table_exists(self):
        self.assertIn("dimension_type", self.tables)

    def test_dimension_value_table_exists(self):
        self.assertIn("dimension_value", self.tables)

    def test_gl_entry_dimension_table_exists(self):
        self.assertIn("gl_entry_dimension", self.tables)

    # Collaboration
    def test_comment_table_exists(self):
        self.assertIn("comment", self.tables)

    def test_comment_mention_table_exists(self):
        self.assertIn("comment_mention", self.tables)

    def test_assignment_table_exists(self):
        self.assertIn("assignment", self.tables)

    def test_workflow_table_exists(self):
        self.assertIn("workflow", self.tables)

    def test_workflow_state_table_exists(self):
        self.assertIn("workflow_state", self.tables)

    def test_workflow_transition_table_exists(self):
        self.assertIn("workflow_transition", self.tables)

    def test_workflow_instance_table_exists(self):
        self.assertIn("workflow_instance", self.tables)

    def test_workflow_action_log_table_exists(self):
        self.assertIn("workflow_action_log", self.tables)

    # Files & Audit
    def test_file_table_exists(self):
        self.assertIn("file", self.tables)

    def test_file_attachment_table_exists(self):
        self.assertIn("file_attachment", self.tables)

    def test_audit_log_table_exists(self):
        self.assertIn("audit_log", self.tables)

    # Snapshots
    def test_account_balance_snapshot_table_exists(self):
        self.assertIn("account_balance_snapshot", self.tables)

    def test_stock_balance_snapshot_table_exists(self):
        self.assertIn("stock_balance_snapshot", self.tables)

    def test_minimum_90_tables(self):
        """El esquema debe tener al menos 90 tablas."""
        self.assertGreaterEqual(len(self.tables), 90)


# -------------------------------------------------------------------------------------
# Tests: Campos de GLEntry — multi-ledger y dimensiones analiticas
# -------------------------------------------------------------------------------------
class TestGLEntrySchema(unittest.TestCase):
    """Verifica que gl_entry tiene todos los campos requeridos."""

    def setUp(self):
        self.app = create_app(configuracion)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.ctx = self.app.app_context()
        self.ctx.push()
        from cacao_accounting.database import database
        from sqlalchemy import inspect

        database.create_all()
        inspector = inspect(database.engine)
        self.columns = {c["name"] for c in inspector.get_columns("gl_entry")}

    def tearDown(self):
        self.ctx.pop()

    def test_gl_entry_has_posting_date(self):
        self.assertIn("posting_date", self.columns)

    def test_gl_entry_has_company(self):
        self.assertIn("company", self.columns)

    def test_gl_entry_has_ledger_id_for_multi_ledger(self):
        """ledger_id permite multi-ledger: Fiscal, NIIF, Board Review, etc."""
        self.assertIn("ledger_id", self.columns)

    def test_gl_entry_has_account_id(self):
        self.assertIn("account_id", self.columns)

    def test_gl_entry_has_debit(self):
        self.assertIn("debit", self.columns)

    def test_gl_entry_has_credit(self):
        self.assertIn("credit", self.columns)

    def test_gl_entry_has_multicurrency_debit(self):
        self.assertIn("debit_in_account_currency", self.columns)

    def test_gl_entry_has_multicurrency_credit(self):
        self.assertIn("credit_in_account_currency", self.columns)

    def test_gl_entry_has_exchange_rate(self):
        self.assertIn("exchange_rate", self.columns)

    def test_gl_entry_has_account_currency(self):
        self.assertIn("account_currency", self.columns)

    def test_gl_entry_has_company_currency(self):
        self.assertIn("company_currency", self.columns)

    def test_gl_entry_has_party_type(self):
        self.assertIn("party_type", self.columns)

    def test_gl_entry_has_party_id(self):
        self.assertIn("party_id", self.columns)

    def test_gl_entry_has_voucher_type(self):
        self.assertIn("voucher_type", self.columns)

    def test_gl_entry_has_voucher_id(self):
        self.assertIn("voucher_id", self.columns)

    def test_gl_entry_has_cost_center_dimension(self):
        """Centro de Costos como dimension analitica primaria."""
        self.assertIn("cost_center_code", self.columns)

    def test_gl_entry_has_unit_dimension(self):
        """Unidad de Negocio como dimension analitica primaria (requerimiento explicito)."""
        self.assertIn("unit_code", self.columns)

    def test_gl_entry_has_project_dimension(self):
        """Proyecto como dimension analitica primaria."""
        self.assertIn("project_code", self.columns)

    def test_gl_entry_has_fiscal_year_id(self):
        self.assertIn("fiscal_year_id", self.columns)

    def test_gl_entry_has_is_cancelled(self):
        self.assertIn("is_cancelled", self.columns)

    def test_gl_entry_has_audit_fields(self):
        self.assertIn("created", self.columns)
        self.assertIn("created_by", self.columns)
        self.assertIn("modified", self.columns)
        self.assertIn("modified_by", self.columns)


# -------------------------------------------------------------------------------------
# Tests: Book (multi-ledger) — Fiscal, NIIF, Board Review
# -------------------------------------------------------------------------------------
class TestBookMultiLedger(unittest.TestCase):
    """Verifica que Book soporta multiples libros contables paralelos."""

    def setUp(self):
        self.app = create_app(configuracion)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.ctx = self.app.app_context()
        self.ctx.push()
        from cacao_accounting.database import database
        from sqlalchemy import inspect

        database.create_all()
        inspector = inspect(database.engine)
        self.columns = {c["name"] for c in inspector.get_columns("book")}

    def tearDown(self):
        self.ctx.pop()

    def test_book_has_code(self):
        self.assertIn("code", self.columns)

    def test_book_has_name(self):
        self.assertIn("name", self.columns)

    def test_book_has_entity(self):
        self.assertIn("entity", self.columns)

    def test_book_has_currency_for_multi_currency_ledger(self):
        """Cada libro puede tener su propia moneda (ej: NIIF en USD)."""
        self.assertIn("currency", self.columns)

    def test_book_has_is_primary(self):
        """Permite identificar el libro primario (fuente de verdad)."""
        self.assertIn("is_primary", self.columns)

    def test_book_has_mapping_rules(self):
        """Soporte para reglas de ajuste entre libros (JSON)."""
        self.assertIn("mapping_rules", self.columns)


# -------------------------------------------------------------------------------------
# Tests: AccountingPeriod — con is_closed y fiscal_year_id
# -------------------------------------------------------------------------------------
class TestAccountingPeriodSchema(unittest.TestCase):
    """Verifica que accounting_period tiene los campos extendidos."""

    def setUp(self):
        self.app = create_app(configuracion)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.ctx = self.app.app_context()
        self.ctx.push()
        from cacao_accounting.database import database
        from sqlalchemy import inspect

        database.create_all()
        inspector = inspect(database.engine)
        self.columns = {c["name"] for c in inspector.get_columns("accounting_period")}

    def tearDown(self):
        self.ctx.pop()

    def test_accounting_period_has_is_closed(self):
        self.assertIn("is_closed", self.columns)

    def test_accounting_period_has_fiscal_year_id(self):
        self.assertIn("fiscal_year_id", self.columns)


# -------------------------------------------------------------------------------------
# Tests: Accounts — con account_type
# -------------------------------------------------------------------------------------
class TestAccountsSchema(unittest.TestCase):
    """Verifica que accounts tiene el campo account_type para AR/AP."""

    def setUp(self):
        self.app = create_app(configuracion)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.ctx = self.app.app_context()
        self.ctx.push()
        from cacao_accounting.database import database
        from sqlalchemy import inspect

        database.create_all()
        inspector = inspect(database.engine)
        self.columns = {c["name"] for c in inspector.get_columns("accounts")}

    def tearDown(self):
        self.ctx.pop()

    def test_accounts_has_account_type(self):
        """account_type: receivable, payable, bank, cash, expense, income, asset, liability."""
        self.assertIn("account_type", self.columns)


# -------------------------------------------------------------------------------------
# Tests: Unit como dimension analitica
# -------------------------------------------------------------------------------------
class TestUnitAsAnalyticDimension(unittest.TestCase):
    """Verifica que Unit esta correctamente vinculada a GLEntry como dimension."""

    def setUp(self):
        self.app = create_app(configuracion)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.ctx = self.app.app_context()
        self.ctx.push()
        from cacao_accounting.database import database, Unit, Unidad

        database.create_all()
        self.Unit = Unit
        self.Unidad = Unidad

    def tearDown(self):
        self.ctx.pop()

    def test_unit_alias_unidad_is_same_class(self):
        """Unidad es un alias de Unit para compatibilidad."""
        self.assertIs(self.Unit, self.Unidad)

    def test_gl_entry_has_unit_code_column(self):
        """unit_code en gl_entry referencia unit.code."""
        from sqlalchemy import inspect
        from cacao_accounting.database import database

        inspector = inspect(database.engine)
        gl_cols = {c["name"] for c in inspector.get_columns("gl_entry")}
        self.assertIn("unit_code", gl_cols)

    def test_unit_table_has_entity_fk(self):
        """Las unidades pertenecen a una entidad/compania."""
        from sqlalchemy import inspect
        from cacao_accounting.database import database

        inspector = inspect(database.engine)
        cols = {c["name"] for c in inspector.get_columns("unit")}
        self.assertIn("entity", cols)


# -------------------------------------------------------------------------------------
# Tests: DocBase — campos transaccionales estandar
# -------------------------------------------------------------------------------------
class TestDocBaseFields(unittest.TestCase):
    """Verifica que los documentos transaccionales tienen los campos DocBase."""

    def setUp(self):
        self.app = create_app(configuracion)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.ctx = self.app.app_context()
        self.ctx.push()
        from cacao_accounting.database import database
        from sqlalchemy import inspect

        database.create_all()
        self.inspector = inspect(database.engine)

    def tearDown(self):
        self.ctx.pop()

    def _check_docbase_fields(self, table_name: str):
        """Verifica que una tabla tiene todos los campos de DocBase."""
        cols = {c["name"] for c in self.inspector.get_columns(table_name)}
        self.assertIn("docstatus", cols, f"{table_name} missing docstatus")
        self.assertIn("posting_date", cols, f"{table_name} missing posting_date")
        self.assertIn("document_date", cols, f"{table_name} missing document_date")
        self.assertIn("company", cols, f"{table_name} missing company")
        self.assertIn("transaction_currency", cols, f"{table_name} missing transaction_currency")
        self.assertIn("base_currency", cols, f"{table_name} missing base_currency")
        self.assertIn("exchange_rate", cols, f"{table_name} missing exchange_rate")
        self.assertIn("is_reversal", cols, f"{table_name} missing is_reversal")
        self.assertIn("reversal_of", cols, f"{table_name} missing reversal_of")

    def test_purchase_order_has_docbase_fields(self):
        self._check_docbase_fields("purchase_order")

    def test_purchase_invoice_has_docbase_fields(self):
        self._check_docbase_fields("purchase_invoice")

    def test_purchase_receipt_has_docbase_fields(self):
        self._check_docbase_fields("purchase_receipt")

    def test_sales_order_has_docbase_fields(self):
        self._check_docbase_fields("sales_order")

    def test_sales_invoice_has_docbase_fields(self):
        self._check_docbase_fields("sales_invoice")

    def test_delivery_note_has_docbase_fields(self):
        self._check_docbase_fields("delivery_note")

    def test_payment_entry_has_docbase_fields(self):
        self._check_docbase_fields("payment_entry")

    def test_stock_entry_has_docbase_fields(self):
        self._check_docbase_fields("stock_entry")


# -------------------------------------------------------------------------------------
# Tests: NamingSeries — resolve_naming_series_prefix
# -------------------------------------------------------------------------------------
class TestResolveNamingSeriesPrefix(unittest.TestCase):
    """Pruebas unitarias para la resolucion de tokens de series."""

    def test_resolves_full_year_token(self):
        from cacao_accounting.database.helpers import resolve_naming_series_prefix

        result = resolve_naming_series_prefix("SI-*YYYY*-", date(2025, 6, 15))
        self.assertEqual(result, "SI-2025-")

    def test_resolves_short_year_token(self):
        from cacao_accounting.database.helpers import resolve_naming_series_prefix

        result = resolve_naming_series_prefix("SI-*YY*-", date(2025, 6, 15))
        self.assertEqual(result, "SI-25-")

    def test_resolves_month_abbreviation_token(self):
        from cacao_accounting.database.helpers import resolve_naming_series_prefix

        result = resolve_naming_series_prefix("SI-*MMM*-", date(2025, 6, 15))
        self.assertEqual(result, "SI-JUN-")

    def test_resolves_month_number_token(self):
        from cacao_accounting.database.helpers import resolve_naming_series_prefix

        result = resolve_naming_series_prefix("SI-*MM*-", date(2025, 6, 15))
        self.assertEqual(result, "SI-06-")

    def test_resolves_day_token(self):
        from cacao_accounting.database.helpers import resolve_naming_series_prefix

        result = resolve_naming_series_prefix("SI-*DD*-", date(2025, 6, 5))
        self.assertEqual(result, "SI-05-")

    def test_resolves_multiple_tokens_at_once(self):
        from cacao_accounting.database.helpers import resolve_naming_series_prefix

        result = resolve_naming_series_prefix(
            "CHOCO-SI-*YYYY*-*MMM*-", date(2025, 6, 15)
        )
        self.assertEqual(result, "CHOCO-SI-2025-JUN-")

    def test_resolves_all_month_abbreviations(self):
        """Verifica que los 12 meses tienen abreviaturas correctas."""
        from cacao_accounting.database.helpers import resolve_naming_series_prefix

        expected = {
            1: "ENE", 2: "FEB", 3: "MAR", 4: "ABR",
            5: "MAY", 6: "JUN", 7: "JUL", 8: "AGO",
            9: "SEP", 10: "OCT", 11: "NOV", 12: "DIC",
        }
        for month, abbr in expected.items():
            result = resolve_naming_series_prefix("*MMM*", date(2025, month, 1))
            self.assertEqual(result, abbr, f"Month {month} should be {abbr}")

    def test_no_tokens_returns_template_unchanged(self):
        from cacao_accounting.database.helpers import resolve_naming_series_prefix

        result = resolve_naming_series_prefix("CHOCO-SI-", date(2025, 6, 15))
        self.assertEqual(result, "CHOCO-SI-")

    def test_posting_date_year_2000_resolves_correctly(self):
        """Verifica que anios de cuatro digitos se resuelven correctamente."""
        from cacao_accounting.database.helpers import resolve_naming_series_prefix

        result = resolve_naming_series_prefix("*YYYY*", date(2000, 1, 1))
        self.assertEqual(result, "2000")


# -------------------------------------------------------------------------------------
# Tests: format_sequence_value — padding
# -------------------------------------------------------------------------------------
class TestFormatSequenceValue(unittest.TestCase):
    """Pruebas del formateador de valores de secuencia."""

    def test_pads_with_zeros(self):
        from cacao_accounting.database.helpers import format_sequence_value

        self.assertEqual(format_sequence_value(1, 5), "00001")

    def test_pads_larger_value(self):
        from cacao_accounting.database.helpers import format_sequence_value

        self.assertEqual(format_sequence_value(999, 5), "00999")

    def test_no_padding_needed(self):
        from cacao_accounting.database.helpers import format_sequence_value

        self.assertEqual(format_sequence_value(12345, 5), "12345")

    def test_exceeds_padding_returns_full_number(self):
        from cacao_accounting.database.helpers import format_sequence_value

        self.assertEqual(format_sequence_value(123456, 5), "123456")

    def test_zero_with_padding(self):
        from cacao_accounting.database.helpers import format_sequence_value

        self.assertEqual(format_sequence_value(0, 5), "00000")

    def test_padding_8_digits(self):
        from cacao_accounting.database.helpers import format_sequence_value

        self.assertEqual(format_sequence_value(1, 8), "00000001")


# -------------------------------------------------------------------------------------
# Tests: Sequence — get_next_sequence_value
# -------------------------------------------------------------------------------------
class TestGetNextSequenceValue(unittest.TestCase):
    """Pruebas del contador de secuencias."""

    def setUp(self):
        self.app = create_app(configuracion)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.ctx = self.app.app_context()
        self.ctx.push()
        from cacao_accounting.database import database

        database.create_all()
        self.database = database

    def tearDown(self):
        self.database.session.rollback()
        self.ctx.pop()

    def _create_sequence(self, name="test_seq", current_value=0, increment=1, padding=5):
        from cacao_accounting.database import Sequence

        seq = Sequence(name=name, current_value=current_value, increment=increment, padding=padding)
        self.database.session.add(seq)
        self.database.session.flush()
        return seq

    def test_increments_sequence_by_one(self):
        from cacao_accounting.database.helpers import get_next_sequence_value

        seq = self._create_sequence()
        next_val = get_next_sequence_value(seq.id)
        self.assertEqual(next_val, 1)

    def test_increments_sequence_consecutively(self):
        from cacao_accounting.database.helpers import get_next_sequence_value

        seq = self._create_sequence()
        val1 = get_next_sequence_value(seq.id)
        val2 = get_next_sequence_value(seq.id)
        val3 = get_next_sequence_value(seq.id)
        self.assertEqual(val1, 1)
        self.assertEqual(val2, 2)
        self.assertEqual(val3, 3)

    def test_custom_increment(self):
        from cacao_accounting.database.helpers import get_next_sequence_value

        seq = self._create_sequence(increment=10)
        val = get_next_sequence_value(seq.id)
        self.assertEqual(val, 10)

    def test_raises_if_sequence_not_found(self):
        from cacao_accounting.database.helpers import get_next_sequence_value

        with self.assertRaises(ValueError):
            get_next_sequence_value("nonexistent-id")


# -------------------------------------------------------------------------------------
# Tests: generate_identifier — integracion completa
# -------------------------------------------------------------------------------------
class TestGenerateIdentifier(unittest.TestCase):
    """Pruebas de integracion del generador de identificadores."""

    def setUp(self):
        self.app = create_app(configuracion)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.ctx = self.app.app_context()
        self.ctx.push()
        from cacao_accounting.database import database

        database.create_all()
        self.database = database

    def tearDown(self):
        self.database.session.rollback()
        self.ctx.pop()

    def _create_naming_series(self, template, entity_type="sales_invoice"):
        from cacao_accounting.database import NamingSeries

        ns = NamingSeries(
            name="Test Series",
            entity_type=entity_type,
            prefix_template=template,
            is_active=True,
        )
        self.database.session.add(ns)
        self.database.session.flush()
        return ns

    def _create_sequence(self, name="test_seq"):
        from cacao_accounting.database import Sequence

        seq = Sequence(name=name, current_value=0, increment=1, padding=5)
        self.database.session.add(seq)
        self.database.session.flush()
        return seq

    def test_generates_identifier_with_series_and_sequence(self):
        from cacao_accounting.database.helpers import generate_identifier

        ns = self._create_naming_series("CHOCO-SI-*YYYY*-*MMM*-")
        seq = self._create_sequence()
        posting = date(2025, 6, 15)

        identifier = generate_identifier(
            entity_type="sales_invoice",
            entity_id="fake-entity-id",
            posting_date=posting,
            naming_series_id=ns.id,
            sequence_id=seq.id,
        )

        self.assertEqual(identifier, "CHOCO-SI-2025-JUN-00001")

    def test_identifier_is_logged_in_audit_table(self):
        from cacao_accounting.database import GeneratedIdentifierLog
        from cacao_accounting.database.helpers import generate_identifier

        ns = self._create_naming_series("LOG-*YYYY*-")
        seq = self._create_sequence("log_seq")
        posting = date(2025, 1, 1)

        identifier = generate_identifier(
            entity_type="purchase_invoice",
            entity_id="fake-pi-id",
            posting_date=posting,
            naming_series_id=ns.id,
            sequence_id=seq.id,
        )

        log_entry = self.database.session.execute(
            self.database.select(GeneratedIdentifierLog).filter_by(
                full_identifier=identifier
            )
        ).scalar_one_or_none()

        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.entity_type, "purchase_invoice")
        self.assertEqual(log_entry.posting_date, posting)

    def test_sequential_identifiers_are_unique(self):
        from cacao_accounting.database.helpers import generate_identifier

        ns = self._create_naming_series("SI-*YYYY*-")
        seq = self._create_sequence("uniq_seq")

        ids = [
            generate_identifier(
                entity_type="sales_invoice",
                entity_id=f"id-{i}",
                posting_date=date(2025, 6, 15),
                naming_series_id=ns.id,
                sequence_id=seq.id,
            )
            for i in range(5)
        ]

        self.assertEqual(len(ids), len(set(ids)), "Los identificadores deben ser unicos")

    def test_raises_if_naming_series_not_found(self):
        from cacao_accounting.database.helpers import generate_identifier

        with self.assertRaises(ValueError):
            generate_identifier(
                entity_type="sales_invoice",
                entity_id="fake-id",
                posting_date=date(2025, 6, 15),
                naming_series_id="nonexistent-id",
                sequence_id=None,
            )

    def test_raises_if_sequence_not_found(self):
        from cacao_accounting.database.helpers import generate_identifier

        with self.assertRaises(ValueError):
            generate_identifier(
                entity_type="sales_invoice",
                entity_id="fake-id",
                posting_date=date(2025, 6, 15),
                naming_series_id=None,
                sequence_id="nonexistent-seq-id",
            )

    def test_generates_different_identifiers_per_year(self):
        """Identifiers generated for different years must differ."""
        from cacao_accounting.database.helpers import generate_identifier

        ns = self._create_naming_series("SI-*YYYY*-")
        seq2025 = self._create_sequence("seq2025")
        seq2026 = self._create_sequence("seq2026")

        id_2025 = generate_identifier(
            entity_type="sales_invoice",
            entity_id="id-2025",
            posting_date=date(2025, 12, 31),
            naming_series_id=ns.id,
            sequence_id=seq2025.id,
        )
        id_2026 = generate_identifier(
            entity_type="sales_invoice",
            entity_id="id-2026",
            posting_date=date(2026, 1, 1),
            naming_series_id=ns.id,
            sequence_id=seq2026.id,
        )

        self.assertIn("2025", id_2025)
        self.assertIn("2026", id_2026)
        self.assertNotEqual(id_2025, id_2026)


# -------------------------------------------------------------------------------------
# Tests: should_reset_sequence / reset_sequence
# -------------------------------------------------------------------------------------
class TestSequenceReset(unittest.TestCase):
    """Pruebas de la politica de reinicio de secuencias."""

    def setUp(self):
        self.app = create_app(configuracion)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.ctx = self.app.app_context()
        self.ctx.push()
        from cacao_accounting.database import database

        database.create_all()
        self.database = database

    def tearDown(self):
        self.database.session.rollback()
        self.ctx.pop()

    def _create_sequence(self, reset_policy="never", current_value=100):
        from cacao_accounting.database import Sequence

        seq = Sequence(
            name="reset_test_seq",
            current_value=current_value,
            increment=1,
            padding=5,
            reset_policy=reset_policy,
        )
        self.database.session.add(seq)
        self.database.session.flush()
        return seq

    def _create_log_entry(self, sequence_id, posting_date):
        from cacao_accounting.database import GeneratedIdentifierLog

        log_entry = GeneratedIdentifierLog(
            entity_type="test",
            entity_id="test-id",
            full_identifier=f"TEST-{posting_date.isoformat()}",
            sequence_id=sequence_id,
            posting_date=posting_date,
        )
        self.database.session.add(log_entry)
        self.database.session.flush()

    def test_never_policy_never_resets(self):
        from cacao_accounting.database.helpers import should_reset_sequence

        seq = self._create_sequence(reset_policy="never")
        self._create_log_entry(seq.id, date(2024, 12, 31))
        result = should_reset_sequence(seq.id, date(2025, 1, 1))
        self.assertFalse(result)

    def test_yearly_policy_resets_on_new_year(self):
        from cacao_accounting.database.helpers import should_reset_sequence

        seq = self._create_sequence(reset_policy="yearly")
        self._create_log_entry(seq.id, date(2024, 12, 31))
        result = should_reset_sequence(seq.id, date(2025, 1, 1))
        self.assertTrue(result)

    def test_yearly_policy_no_reset_same_year(self):
        from cacao_accounting.database.helpers import should_reset_sequence

        seq = self._create_sequence(reset_policy="yearly")
        self._create_log_entry(seq.id, date(2025, 6, 1))
        result = should_reset_sequence(seq.id, date(2025, 12, 31))
        self.assertFalse(result)

    def test_monthly_policy_resets_on_new_month(self):
        from cacao_accounting.database.helpers import should_reset_sequence

        seq = self._create_sequence(reset_policy="monthly")
        self._create_log_entry(seq.id, date(2025, 5, 31))
        result = should_reset_sequence(seq.id, date(2025, 6, 1))
        self.assertTrue(result)

    def test_monthly_policy_no_reset_same_month(self):
        from cacao_accounting.database.helpers import should_reset_sequence

        seq = self._create_sequence(reset_policy="monthly")
        self._create_log_entry(seq.id, date(2025, 6, 1))
        result = should_reset_sequence(seq.id, date(2025, 6, 30))
        self.assertFalse(result)

    def test_reset_sequence_sets_value_to_zero(self):
        from cacao_accounting.database import Sequence
        from cacao_accounting.database.helpers import reset_sequence

        seq = self._create_sequence(current_value=99)
        reset_sequence(seq.id)
        updated = self.database.session.get(Sequence, seq.id)
        self.assertEqual(updated.current_value, 0)

    def test_reset_sequence_raises_if_not_found(self):
        from cacao_accounting.database.helpers import reset_sequence

        with self.assertRaises(ValueError):
            reset_sequence("nonexistent-sequence-id")


# -------------------------------------------------------------------------------------
# Tests: Backward compatibility — aliases
# -------------------------------------------------------------------------------------
def test_modulos_is_alias_for_modules():
    """Modulos es un alias de Modules para compatibilidad."""
    from cacao_accounting.database import Modulos, Modules

    assert Modulos is Modules


def test_unidad_is_alias_for_unit():
    """Unidad es un alias de Unit para compatibilidad."""
    from cacao_accounting.database import Unidad, Unit

    assert Unidad is Unit


def test_entity_has_tipo_entidad_lista():
    """Entity.tipo_entidad_lista es requerido por SetupCompanyForm."""
    from cacao_accounting.database import Entity

    assert hasattr(Entity, "tipo_entidad_lista")
    assert isinstance(Entity.tipo_entidad_lista, list)
    assert len(Entity.tipo_entidad_lista) > 0


# -------------------------------------------------------------------------------------
# Tests: Importaciones del modulo database
# -------------------------------------------------------------------------------------
def test_all_domain_models_importable():
    """Todos los modelos del dominio se pueden importar correctamente."""
    from cacao_accounting.database import (  # noqa: F401
        # Core
        CacaoConfig, Currency, ExchangeRate,
        # Auth
        User, Roles, RolesAccess, RolesUser, Modules, Modulos,
        # Company
        Entity, Unit, Unidad, Book,
        # Accounting
        FiscalYear, AccountingPeriod, Accounts, CostCenter, Project,
        # GL
        GLEntry, GLBase, ComprobanteContable, ComprobanteContableDetalle,
        # Series
        Serie, NamingSeries, Sequence, SeriesSequenceMap, GeneratedIdentifierLog,
        # Party
        Party, Contact, Address, PartyContact, PartyAddress, CompanyParty,
        # Inventory
        UOM, Item, ItemUOMConversion, Warehouse, Batch, SerialNumber,
        StockEntry, StockEntryItem, StockLedgerEntry, StockBin, StockValuationLayer,
        # Purchasing
        PurchaseOrder, PurchaseOrderItem, PurchaseReceipt, PurchaseReceiptItem,
        PurchaseInvoice, PurchaseInvoiceItem,
        # Sales
        SalesOrder, SalesOrderItem, DeliveryNote, DeliveryNoteItem,
        SalesInvoice, SalesInvoiceItem,
        # Banking
        Bank, BankAccount, PaymentEntry, PaymentReference, BankTransaction,
        # Account mapping
        ItemAccount, PartyAccount, CompanyDefaultAccount,
        # Tax & Pricing
        Tax, TaxTemplate, TaxTemplateItem, PriceList, ItemPrice,
        # Reconciliation
        Reconciliation, ReconciliationItem,
        # GR/IR
        GRIRReconciliation,
        # Multi-ledger
        LedgerMappingRule,
        # Revaluation & Period Close
        ExchangeRevaluation, ExchangeRevaluationItem,
        PeriodCloseRun, PeriodCloseCheck,
        # Dimensions
        DimensionType, DimensionValue, GLEntryDimension,
        # Collaboration
        Comment, CommentMention, Assignment,
        Workflow, WorkflowState, WorkflowTransition,
        WorkflowInstance, WorkflowActionLog,
        # Files
        File, FileAttachment,
        # Audit & Snapshots
        AuditLog, AccountBalanceSnapshot, StockBalanceSnapshot,
    )
    # If we reach here without ImportError, all imports succeeded
    assert True
