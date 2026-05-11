# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo de Caja y Bancos."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from datetime import date
from decimal import Decimal
from typing import cast

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import login_required

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.bancos.reconciliation_service import (
    BankReconciliationError,
    BankReconciliationMatch,
    BankReconciliationRequest,
    find_bank_reconciliation_candidates,
    reconcile_bank_items,
)
from cacao_accounting.bancos.statement_service import (
    BankStatementError,
    apply_bank_matching_rule,
    import_bank_statement,
)
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankMatchingRule,
    BankTransaction,
    PaymentEntry,
    PaymentReference,
    PurchaseInvoice,
    ReconciliationItem,
    SalesInvoice,
    database,
)
from cacao_accounting.database.helpers import get_active_naming_series
from cacao_accounting.contabilidad.posting import PostingError, cancel_document, post_bank_transaction, submit_document
from cacao_accounting.document_flow.service import compute_outstanding_amount, refresh_outstanding_amount_cache
from cacao_accounting.document_flow.status import _
from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier
from cacao_accounting.decorators import modulo_activo
from cacao_accounting.version import APPNAME

bancos = Blueprint("bancos", __name__, template_folder="templates")


def _series_choices(entity_type: str, company: str | None) -> list[tuple[str, str]]:
    """Construye las opciones de series activas para un doctype y compania."""
    if not company:
        return [("", "")]

    return [("", "")] + [
        (str(series.id), f"{series.name} ({series.prefix_template})")
        for series in get_active_naming_series(entity_type=entity_type, company=company)
    ]


@bancos.route("/")
@bancos.route("/caja")
@bancos.route("/tesoreria")
@bancos.route("/bancos")
@bancos.route("/cash")
@modulo_activo("cash")
@login_required
def bancos_():
    """Pantalla principal del modulo de bancos."""
    return render_template("bancos.html")


@bancos.route("/bank/list")
@modulo_activo("cash")
@login_required
def bancos_banco_lista():
    """Listado de bancos."""
    consulta = database.paginate(
        database.select(Bank),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Bancos - " + APPNAME
    return render_template("bancos/banco_lista.html", consulta=consulta, titulo=titulo)


@bancos.route("/bank-account/list")
@modulo_activo("cash")
@login_required
def bancos_cuenta_bancaria_lista():
    """Listado de cuentas bancarias."""
    consulta = database.paginate(
        database.select(BankAccount),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Cuentas Bancarias - " + APPNAME
    return render_template("bancos/banco_cuenta_lista.html", consulta=consulta, titulo=titulo)


@bancos.route("/payment/list")
@modulo_activo("cash")
@login_required
def bancos_pago_lista():
    """Listado de entradas de pago."""
    consulta = database.paginate(
        database.select(PaymentEntry).filter(PaymentEntry.payment_type.in_(("receive", "pay"))),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Pagos - " + APPNAME
    return render_template("bancos/pago_lista.html", consulta=consulta, titulo=titulo)


@bancos.route("/transfer/list")
@modulo_activo("cash")
@login_required
def bancos_transferencia_lista():
    """Listado de transferencias internas."""
    consulta = database.paginate(
        database.select(PaymentEntry).filter_by(payment_type="internal_transfer"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Transferencias Internas - " + APPNAME
    return render_template("bancos/pago_lista.html", consulta=consulta, titulo=titulo, is_transfer_list=True)


@bancos.route("/bank-transaction/list")
@modulo_activo("cash")
@login_required
def bancos_transaccion_lista():
    """Listado de transacciones bancarias."""
    consulta = database.paginate(
        database.select(BankTransaction),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Transacciones Bancarias - " + APPNAME
    return render_template("bancos/transaccion_lista.html", consulta=consulta, titulo=titulo)


@bancos.route("/bank-transaction/debit-note/list")
@modulo_activo("cash")
@login_required
def bancos_nota_debito_lista():
    """Listado de notas de débito bancario (retiros)."""
    consulta = database.paginate(
        database.select(BankTransaction).filter(BankTransaction.withdrawal.is_not(None)),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Notas de Débito Bancario - " + APPNAME
    return render_template(
        "bancos/transaccion_lista.html",
        consulta=consulta,
        titulo=titulo,
        page_heading="Listado de Notas de Débito Bancario",
        new_url=url_for("bancos.bancos_nota_debito_nueva"),
    )


@bancos.route("/bank-transaction/credit-note/list")
@modulo_activo("cash")
@login_required
def bancos_nota_credito_lista():
    """Listado de notas de crédito bancario (depósitos)."""
    consulta = database.paginate(
        database.select(BankTransaction).filter(BankTransaction.deposit.is_not(None)),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Notas de Crédito Bancario - " + APPNAME
    return render_template(
        "bancos/transaccion_lista.html",
        consulta=consulta,
        titulo=titulo,
        page_heading="Listado de Notas de Crédito Bancario",
        new_url=url_for("bancos.bancos_nota_credito_nueva"),
    )


def _crear_nota_bancaria(note_kind: str):
    """Crea una transacción bancaria manual como nota de débito/crédito."""
    company = request.form.get("company") or request.args.get("company") or None
    if request.method == "POST":
        amount = _form_decimal("amount")
        if amount <= 0:
            abort(409)
        bank_account_id = request.form.get("bank_account_id", "")
        bank_account = database.session.get(BankAccount, bank_account_id)
        if not bank_account:
            abort(400)
        if company and bank_account.company != company:
            abort(409)
        transaction = BankTransaction(
            bank_account_id=bank_account_id,
            posting_date=request.form.get("posting_date") or None,
            description=request.form.get("description") or None,
            reference_number=request.form.get("reference_number") or None,
            deposit=amount if note_kind == "credit" else None,
            withdrawal=amount if note_kind == "debit" else None,
        )
        database.session.add(transaction)
        database.session.flush()
        try:
            post_bank_transaction(transaction)
            database.session.commit()
            flash(_("Nota bancaria registrada correctamente y registrada en el libro mayor."), "success")
        except PostingError as exc:
            database.session.rollback()
            flash(_(str(exc)), "danger")
            if note_kind == "credit":
                return redirect(url_for("bancos.bancos_nota_credito_nueva"))
            return redirect(url_for("bancos.bancos_nota_debito_nueva"))
        list_view = "bancos.bancos_nota_credito_lista" if note_kind == "credit" else "bancos.bancos_nota_debito_lista"
        return redirect(url_for(list_view))
    cuentas_query = database.select(BankAccount).filter_by(is_active=True)
    if company:
        cuentas_query = cuentas_query.filter_by(company=company)
    cuentas = database.session.execute(cuentas_query).scalars().all()
    return render_template(
        "bancos/transaccion_nueva.html",
        titulo=("Nueva Nota de Crédito Bancario - " if note_kind == "credit" else "Nueva Nota de Débito Bancario - ")
        + APPNAME,
        note_kind=note_kind,
        cuentas=cuentas,
        company=company,
    )


@bancos.route("/bank-transaction/reconcile", methods=["POST"])
@modulo_activo("cash")
@login_required
def bancos_transaccion_reconciliar():
    """Marca transacciones bancarias seleccionadas como conciliadas."""
    transaction_ids = request.form.getlist("transaction_id")
    if not transaction_ids:
        abort(400)

    transactions = (
        database.session.execute(database.select(BankTransaction).filter(BankTransaction.id.in_(transaction_ids)))
        .scalars()
        .all()
    )
    if not transactions:
        abort(404)
    if any(transaction.is_reconciled for transaction in transactions):
        abort(409)

    company = None
    for transaction in transactions:
        bank_account = database.session.get(BankAccount, transaction.bank_account_id)
        if not bank_account:
            abort(404)
        if company is None:
            company = bank_account.company
        elif bank_account.company != company:
            abort(409)
        duplicated_item = database.session.execute(
            database.select(ReconciliationItem.id)
            .filter_by(reference_type="bank_transaction", reference_id=transaction.id)
            .limit(1)
        ).scalar_one_or_none()
        if duplicated_item:
            abort(409)

    try:
        reconcile_bank_items(
            BankReconciliationRequest(
                company=str(company),
                reconciliation_date=date.today(),
                matches=[
                    BankReconciliationMatch(
                        bank_transaction_id=transaction.id,
                        target_type="gl_entry",
                        target_id=str(request.form.get(f"target_id_{transaction.id}") or ""),
                        allocated_amount=transaction.deposit if transaction.deposit is not None else transaction.withdrawal,
                    )
                    for transaction in transactions
                    if request.form.get(f"target_id_{transaction.id}")
                ],
            )
        )
    except BankReconciliationError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for("bancos.bancos_conciliacion_bancaria"))

    database.session.commit()
    flash(_("Transacciones bancarias conciliadas correctamente."), "success")
    return redirect(url_for("bancos.bancos_transaccion_lista"))


@bancos.route("/bank-reconciliation")
@modulo_activo("cash")
@login_required
def bancos_conciliacion_bancaria():
    """Panel de conciliacion bancaria con transacciones pendientes."""
    company = request.args.get("company") or None
    query = database.select(BankTransaction).filter_by(is_reconciled=False)
    if company:
        query = query.join(BankAccount, BankAccount.id == BankTransaction.bank_account_id).filter(
            BankAccount.company == company
        )
    transactions = database.session.execute(query.order_by(BankTransaction.posting_date)).scalars().all()
    suggestions = {transaction.id: find_bank_reconciliation_candidates(transaction.id) for transaction in transactions}
    return render_template(
        "bancos/conciliacion_bancaria.html",
        titulo="Conciliación Bancaria - " + APPNAME,
        transactions=transactions,
        suggestions=suggestions,
        company=company,
    )


@bancos.route("/bank-reconciliation/<bank_account_id>")
@modulo_activo("cash")
@login_required
def bancos_conciliacion_bancaria_cuenta(bank_account_id: str):
    """Panel de conciliacion bancaria filtrado por cuenta."""
    bank_account = database.session.get(BankAccount, bank_account_id)
    if not bank_account:
        abort(404)
    transactions = (
        database.session.execute(
            database.select(BankTransaction)
            .filter_by(bank_account_id=bank_account_id, is_reconciled=False)
            .order_by(BankTransaction.posting_date)
        )
        .scalars()
        .all()
    )
    suggestions = {transaction.id: find_bank_reconciliation_candidates(transaction.id) for transaction in transactions}
    return render_template(
        "bancos/conciliacion_bancaria.html",
        titulo="Conciliación Bancaria - " + APPNAME,
        transactions=transactions,
        suggestions=suggestions,
        company=bank_account.company,
    )


@bancos.route("/bank-reconciliation/apply", methods=["POST"])
@modulo_activo("cash")
@login_required
def bancos_conciliacion_bancaria_aplicar() -> ResponseReturnValue:
    """Aplica conciliaciones bancarias seleccionadas."""
    company = request.form.get("company") or "cacao"
    matches: list[BankReconciliationMatch] = []
    for transaction_id in request.form.getlist("bank_transaction_id"):
        target = request.form.get(f"target_{transaction_id}") or ""
        amount = _form_decimal(f"amount_{transaction_id}")
        if not target or amount <= 0:
            continue
        target_type, target_id = target.split(":", 1)
        matches.append(
            BankReconciliationMatch(
                bank_transaction_id=transaction_id,
                target_type=target_type,
                target_id=target_id,
                allocated_amount=amount,
            )
        )
    try:
        reconcile_bank_items(BankReconciliationRequest(company=company, reconciliation_date=date.today(), matches=matches))
        database.session.commit()
        flash(_("Conciliación bancaria aplicada correctamente."), "success")
    except BankReconciliationError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
    return redirect(url_for("bancos.bancos_conciliacion_bancaria", company=company))


@bancos.route("/bank-statement/import", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_extracto_importar():
    """Importa extractos bancarios CSV con preview."""
    accounts = (
        database.session.execute(database.select(BankAccount).filter_by(is_active=True).order_by(BankAccount.account_name))
        .scalars()
        .all()
    )
    result = None
    if request.method == "POST":
        mapping = {
            "date": request.form.get("date_column") or "date",
            "reference": request.form.get("reference_column") or "reference",
            "description": request.form.get("description_column") or "description",
            "deposit": request.form.get("deposit_column") or "deposit",
            "withdrawal": request.form.get("withdrawal_column") or "withdrawal",
        }
        try:
            result = import_bank_statement(
                request.files["statement_file"],
                mapping,
                request.form.get("bank_account_id") or "",
                preview=request.form.get("action") == "preview",
            )
            if request.form.get("action") == "import":
                database.session.commit()
                flash(_("Extracto importado correctamente."), "success")
                return redirect(url_for("bancos.bancos_transaccion_lista"))
        except (BankStatementError, KeyError) as exc:
            database.session.rollback()
            flash(_(str(exc)), "danger")
    return render_template(
        "bancos/extracto_importar.html", accounts=accounts, result=result, titulo=_("Importar Extracto Bancario")
    )


@bancos.route("/bank-matching-rules", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_reglas_matching():
    """Administra reglas de matching bancario."""
    accounts = (
        database.session.execute(database.select(BankAccount).filter_by(is_active=True).order_by(BankAccount.account_name))
        .scalars()
        .all()
    )
    if request.method == "POST":
        rule = BankMatchingRule(
            company=request.form.get("company") or "",
            bank_account_id=request.form.get("bank_account_id") or None,
            name=request.form.get("name") or "",
            days_tolerance=int(request.form.get("days_tolerance") or 7),
            amount_tolerance=Decimal(request.form.get("amount_tolerance") or "0"),
            reference_contains=request.form.get("reference_contains") or None,
            priority=int(request.form.get("priority") or 100),
            is_active=bool(request.form.get("is_active", "1")),
        )
        database.session.add(rule)
        database.session.commit()
        flash(_("Regla de matching creada correctamente."), "success")
        return redirect(url_for("bancos.bancos_reglas_matching"))
    rules = database.session.execute(database.select(BankMatchingRule).order_by(BankMatchingRule.priority)).scalars().all()
    return render_template(
        "bancos/reglas_matching.html", accounts=accounts, rules=rules, titulo=_("Reglas de Matching Bancario")
    )


@bancos.route("/bank-matching-rules/<rule_id>/run", methods=["POST"])
@modulo_activo("cash")
@login_required
def bancos_regla_matching_ejecutar(rule_id: str):
    """Ejecuta una regla de matching para una cuenta y rango."""
    try:
        date_from = date.fromisoformat(request.form.get("date_from") or date.today().isoformat())
        date_to = date.fromisoformat(request.form.get("date_to") or date.today().isoformat())
        result = apply_bank_matching_rule(rule_id, request.form.get("bank_account_id") or "", (date_from, date_to))
        flash(
            _("Regla ejecutada: {count} transacciones evaluadas.").format(count=len(result.candidates_by_transaction)),
            "success",
        )
    except BankStatementError as exc:
        flash(_(str(exc)), "danger")
    return redirect(url_for("bancos.bancos_reglas_matching"))


@bancos.route("/bank-transaction/debit-note/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_nota_debito_nueva():
    """Formulario de nota de débito bancaria."""
    return _crear_nota_bancaria("debit")


@bancos.route("/bank-transaction/credit-note/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_nota_credito_nueva():
    """Formulario de nota de crédito bancaria."""
    return _crear_nota_bancaria("credit")


@bancos.route("/bank/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_banco_nuevo():
    """Formulario para crear un nuevo banco."""
    from cacao_accounting.bancos.forms import FormularioBanco

    formulario = FormularioBanco()
    titulo = "Nuevo Banco - " + APPNAME
    if formulario.validate_on_submit() or request.method == "POST":
        banco = Bank(
            name=request.form.get("name"),
            swift_code=request.form.get("swift_code"),
        )
        database.session.add(banco)
        database.session.commit()
        return redirect("/cash_management/bank/list")
    return render_template("bancos/banco_nuevo.html", form=formulario, titulo=titulo)


@bancos.route("/bank/<bank_id>")
@modulo_activo("cash")
@login_required
def bancos_banco(bank_id):
    """Detalle de banco."""
    from flask import abort

    registro = database.session.get(Bank, bank_id)
    if not registro:
        abort(404)
    titulo = registro.name + " - " + APPNAME
    return render_template("bancos/banco.html", registro=registro, titulo=titulo)


@bancos.route("/bank-account/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_cuenta_bancaria_nuevo():
    """Formulario para crear una nueva cuenta bancaria."""
    from cacao_accounting.bancos.forms import FormularioCuentaBancaria
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial, obtener_lista_monedas

    formulario = FormularioCuentaBancaria()
    formulario.bank_id.choices = [(b[0].id, b[0].name) for b in database.session.execute(database.select(Bank)).all()]
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    formulario.currency.choices = [("", "")] + obtener_lista_monedas()
    titulo = "Nueva Cuenta Bancaria - " + APPNAME
    if formulario.validate_on_submit() or request.method == "POST":
        cuenta = BankAccount(
            bank_id=request.form.get("bank_id"),
            company=request.form.get("company"),
            account_name=request.form.get("account_name"),
            account_no=request.form.get("account_no"),
            iban=request.form.get("iban"),
            currency=request.form.get("currency") or None,
        )
        database.session.add(cuenta)
        database.session.commit()
        return redirect("/cash_management/bank-account/list")
    return render_template("bancos/banco_cuenta_nuevo.html", form=formulario, titulo=titulo)


@bancos.route("/bank-account/<account_id>")
@modulo_activo("cash")
@login_required
def bancos_cuenta_bancaria(account_id):
    """Detalle de cuenta bancaria."""
    from flask import abort

    registro = database.session.get(BankAccount, account_id)
    if not registro:
        abort(404)
    titulo = registro.account_name + " - " + APPNAME
    return render_template("bancos/banco_cuenta.html", registro=registro, titulo=titulo)


def _form_decimal(field_name: str, default: str = "0") -> Decimal:
    """Convierte un valor de formulario a Decimal."""
    value = request.form.get(field_name)
    return Decimal(str(value if value not in (None, "") else default))


def _invoice_outstanding(invoice) -> Decimal:
    """Devuelve el saldo vivo calculado de una factura."""
    return compute_outstanding_amount(invoice)


def _payment_source_rows(purchase_invoice_ids: list[str], sales_invoice_ids: list[str]) -> list[dict]:
    """Construye las filas origen para el formulario de pago."""
    rows = []
    for invoice_id in purchase_invoice_ids:
        invoice = database.session.get(PurchaseInvoice, invoice_id)
        if invoice:
            rows.append(
                {
                    "reference_type": "purchase_invoice",
                    "label": "Factura de Compra",
                    "document": invoice,
                    "url": url_for("compras.compras_factura_compra", invoice_id=invoice.id),
                }
            )
    for invoice_id in sales_invoice_ids:
        invoice = database.session.get(SalesInvoice, invoice_id)
        if invoice:
            rows.append(
                {
                    "reference_type": "sales_invoice",
                    "label": "Factura de Venta",
                    "document": invoice,
                    "url": url_for("ventas.ventas_factura_venta", invoice_id=invoice.id),
                }
            )
    return rows


def _save_payment_references(payment: PaymentEntry) -> Decimal:
    """Guarda referencias de pago y actualiza saldos vivos de facturas."""
    total_allocated = Decimal("0")
    i = 0
    while request.form.get(f"reference_id_{i}"):
        reference_type = request.form.get(f"reference_type_{i}", "")
        reference_id = request.form.get(f"reference_id_{i}", "")
        allocated = _form_decimal(f"allocated_amount_{i}", "0")
        if allocated <= 0:
            i += 1
            continue
        if reference_type == "purchase_invoice":
            invoice = database.session.get(PurchaseInvoice, reference_id)
        elif reference_type == "sales_invoice":
            invoice = database.session.get(SalesInvoice, reference_id)
        else:
            abort(400)
        if not invoice:
            abort(404)
        invoice = cast(PurchaseInvoice | SalesInvoice, invoice)
        if payment.company and invoice.company and payment.company != invoice.company:
            abort(409)
        outstanding = _invoice_outstanding(invoice)
        if allocated > outstanding:
            abort(409)
        reference = PaymentReference(
            payment_id=payment.id,
            reference_type=reference_type,
            reference_id=reference_id,
            total_amount=invoice.grand_total,
            outstanding_amount=outstanding,
            allocated_amount=allocated,
            allocation_date=payment.posting_date,
        )
        database.session.add(reference)
        invoice.outstanding_amount = outstanding - allocated
        invoice.base_outstanding_amount = invoice.outstanding_amount
        total_allocated += allocated
        i += 1
    return total_allocated


def _refresh_payment_reference_document(reference_type: str, reference_id: str) -> None:
    """Actualiza el cache de saldo pendiente para documentos referenciados."""
    model_map = {
        "purchase_invoice": PurchaseInvoice,
        "sales_invoice": SalesInvoice,
    }
    model = model_map.get(reference_type)
    if not model:
        return
    document = database.session.get(model, reference_id)
    if document:
        refresh_outstanding_amount_cache(document)


@bancos.route("/payment/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_pago_nuevo():
    """Formulario para crear un nuevo pago."""
    from cacao_accounting.bancos.forms import FormularioPago
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.database import ExternalCounter, Party

    formulario = FormularioPago()
    formulario.company.choices = obtener_lista_entidades_por_id_razonsocial()
    selected_company = request.values.get("company") or (
        formulario.company.choices[0][0] if formulario.company.choices else None
    )
    formulario.naming_series.choices = _series_choices("payment_entry", selected_company)
    formulario.bank_account_id.choices = [("", "")] + [
        (str(b[0].id), f"{b[0].account_name} {b[0].account_no or ''}".strip())
        for b in database.session.execute(database.select(BankAccount).filter_by(is_active=True)).all()
    ]
    formulario.party_id.choices = [("", "")] + [
        (str(p[0].id), p[0].name) for p in database.session.execute(database.select(Party)).all()
    ]
    # Contadores externos activos para la compania seleccionada
    counters_query = database.select(ExternalCounter).filter_by(is_active=True)
    if selected_company:
        counters_query = counters_query.filter_by(company=selected_company)
    active_counters = database.session.execute(counters_query).scalars().all()
    formulario.external_counter_id.choices = [("", "— Sin contador externo —")] + [
        (str(c.id), f"{c.name} (siguiente: {c.next_suggested_formatted})") for c in active_counters
    ]

    from_purchase_invoice_ids = request.values.getlist("from_purchase_invoice")
    from_sales_invoice_ids = request.values.getlist("from_sales_invoice")
    facturas_origen = _payment_source_rows(from_purchase_invoice_ids, from_sales_invoice_ids)
    if request.method == "GET" and facturas_origen:
        first = facturas_origen[0]["document"]
        formulario.company.data = first.company
        formulario.party_id.data = getattr(first, "supplier_id", None) or getattr(first, "customer_id", None)
        formulario.party_type.data = "supplier" if facturas_origen[0]["reference_type"] == "purchase_invoice" else "customer"
        formulario.payment_type.data = "pay" if facturas_origen[0]["reference_type"] == "purchase_invoice" else "receive"
        formulario.paid_amount.data = str(
            sum((_invoice_outstanding(row["document"]) for row in facturas_origen), Decimal("0"))
        )
    factura_compra_origen = (
        database.session.get(PurchaseInvoice, from_purchase_invoice_ids[0]) if from_purchase_invoice_ids else None
    )
    factura_venta_origen = database.session.get(SalesInvoice, from_sales_invoice_ids[0]) if from_sales_invoice_ids else None
    titulo = "Nuevo Pago - " + APPNAME
    if request.method == "POST":
        try:
            amount = _form_decimal("paid_amount", "0")
            payment_type = request.form.get("payment_type") or "receive"
            if payment_type == "internal_transfer" and (from_purchase_invoice_ids or from_sales_invoice_ids):
                abort(409)
            if from_purchase_invoice_ids and from_sales_invoice_ids:
                abort(409)
            payment = PaymentEntry(
                payment_type=payment_type,
                company=request.form.get("company") or None,
                posting_date=request.form.get("posting_date") or None,
                bank_account_id=request.form.get("bank_account_id") or None,
                party_type=request.form.get("party_type") or None,
                party_id=request.form.get("party_id") or None,
                remarks=request.form.get("remarks"),
                docstatus=0,
            )
            if payment_type == "pay":
                payment.paid_amount = amount
                payment.base_paid_amount = amount
            elif payment_type == "receive":
                payment.received_amount = amount
                payment.base_received_amount = amount
            else:
                payment.paid_amount = amount
                payment.received_amount = amount
            database.session.add(payment)
            database.session.flush()
            # Contexto para seleccion contextual del contador externo
            ext_context = {
                "payment_type": payment_type,
                "bank_account_id": request.form.get("bank_account_id") or None,
            }
            assign_document_identifier(
                document=payment,
                entity_type="payment_entry",
                posting_date_raw=request.form.get("posting_date"),
                naming_series_id=request.form.get("naming_series") or None,
                external_counter_id=request.form.get("external_counter_id") or None,
                external_number=request.form.get("external_number") or None,
                external_context=ext_context,
            )
            allocated = _save_payment_references(payment)
            if allocated and amount != allocated:
                raise ValueError(_("El monto del pago debe coincidir con el monto asignado a referencias."))
            if amount == 0 and allocated:
                if payment_type == "pay":
                    payment.paid_amount = allocated
                    payment.base_paid_amount = allocated
                else:
                    payment.received_amount = allocated
                    payment.base_received_amount = allocated
            database.session.commit()
            flash("Pago creado correctamente.", "success")
            return redirect(url_for("bancos.bancos_pago", payment_id=payment.id))
        except IdentifierConfigurationError as exc:
            database.session.rollback()
            flash(str(exc), "danger")
    return render_template(
        "bancos/pago_nuevo.html",
        form=formulario,
        titulo=titulo,
        from_purchase_invoice_ids=from_purchase_invoice_ids,
        from_sales_invoice_ids=from_sales_invoice_ids,
        factura_compra_origen=factura_compra_origen,
        factura_venta_origen=factura_venta_origen,
        facturas_origen=facturas_origen,
    )


@bancos.route("/payment/<payment_id>")
@modulo_activo("cash")
@login_required
def bancos_pago(payment_id):
    """Detalle de pago."""
    from flask import abort

    registro = database.session.get(PaymentEntry, payment_id)
    if not registro:
        abort(404)
    titulo = (registro.document_no or payment_id) + " - " + APPNAME
    return render_template("bancos/pago.html", registro=registro, titulo=titulo)


@bancos.route("/payment/<payment_id>/submit", methods=["POST"])
@modulo_activo("cash")
@login_required
def bancos_pago_submit(payment_id: str):
    """Aprueba y contabiliza un pago."""
    registro = database.session.get(PaymentEntry, payment_id)
    if not registro:
        abort(404)
    if registro.docstatus != 0:
        abort(400)
    try:
        submit_document(registro)
        database.session.commit()
    except PostingError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for("bancos.bancos_pago", payment_id=payment_id))
    flash(_("Pago aprobado y contabilizado."), "success")
    return redirect(url_for("bancos.bancos_pago", payment_id=payment_id))


@bancos.route("/payment/<payment_id>/cancel", methods=["POST"])
@modulo_activo("cash")
@login_required
def bancos_pago_cancel(payment_id: str):
    """Cancela un pago con reverso contable."""
    registro = database.session.get(PaymentEntry, payment_id)
    if not registro:
        abort(404)
    if registro.docstatus != 1:
        abort(400)
    try:
        cancel_document(registro)
        references = (
            database.session.execute(database.select(PaymentReference).filter_by(payment_id=registro.id)).scalars().all()
        )
        affected_docs = {
            (ref.reference_type, ref.reference_id) for ref in references if ref.reference_type and ref.reference_id
        }
        for ref in references:
            database.session.delete(ref)
        for reference_type, reference_id in affected_docs:
            _refresh_payment_reference_document(reference_type, reference_id)
        database.session.commit()
    except PostingError as exc:
        database.session.rollback()
        flash(_(str(exc)), "danger")
        return redirect(url_for("bancos.bancos_pago", payment_id=payment_id))
    flash(_("Pago cancelado con reverso contable."), "warning")
    return redirect(url_for("bancos.bancos_pago", payment_id=payment_id))
