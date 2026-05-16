# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo de Caja y Bancos."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from datetime import date
from decimal import Decimal
import json
from typing import cast

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

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
    Accounts,
    Bank,
    BankAccount,
    BankMatchingRule,
    BankTransaction,
    ExternalCounter,
    NamingSeries,
    PaymentEntry,
    PaymentReference,
    PurchaseInvoice,
    ReconciliationItem,
    SalesInvoice,
    SeriesExternalCounterMap,
    User,
    database,
)
from cacao_accounting.database.helpers import get_active_naming_series
from cacao_accounting.contabilidad.posting import PostingError, cancel_document, post_bank_transaction, submit_document
from cacao_accounting.document_flow import create_document_relation, revert_relations_for_target
from cacao_accounting.document_flow.service import compute_outstanding_amount, refresh_outstanding_amount_cache
from cacao_accounting.document_flow.status import _
from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier
from cacao_accounting.decorators import modulo_activo
from cacao_accounting.version import APPNAME

bancos = Blueprint("bancos", __name__, template_folder="templates")

BANCOS_TRANSACCION_LISTA_HTML = "bancos/transaccion_lista.html"
BANCOS_BANCO_CUENTA_NUEVO_HTML = "bancos/banco_cuenta_nuevo.html"
BANCOS_BANCOS_PAGO = "bancos.bancos_pago"


def _series_choices(entity_type: str, company: str | None) -> list[tuple[str, str]]:
    """Construye las opciones de series activas para un doctype y compania."""
    if not company:
        return [("", "")]

    return [("", "")] + [
        (str(series.id), f"{series.name} ({series.prefix_template})")
        for series in get_active_naming_series(entity_type=entity_type, company=company)
    ]


def _validate_bank_account_numbering_defaults(
    *,
    company: str | None,
    naming_series_id: str | None,
    external_counter_id: str | None,
) -> tuple[str | None, str | None]:
    """Valida la serie de pagos y chequera predeterminadas de una cuenta bancaria."""
    if naming_series_id:
        series = database.session.get(NamingSeries, naming_series_id)
        if not series or not series.is_active:
            raise IdentifierConfigurationError("La serie interna seleccionada no existe o está inactiva.")
        if series.entity_type != "payment_entry":
            raise IdentifierConfigurationError("La serie interna debe ser para pagos.")
        if series.company not in (None, company):
            raise IdentifierConfigurationError("La serie interna no pertenece a la compañía indicada.")

    if external_counter_id:
        counter = database.session.get(ExternalCounter, external_counter_id)
        if not counter or not counter.is_active:
            raise IdentifierConfigurationError("La chequera seleccionada no existe o está inactiva.")
        if counter.counter_type != "checkbook":
            raise IdentifierConfigurationError("El contador externo seleccionado debe ser una chequera.")
        if counter.company != company:
            raise IdentifierConfigurationError("La chequera no pertenece a la compañía indicada.")

    return naming_series_id, external_counter_id


def _ensure_bank_account_counter_mapping(bank_account: BankAccount) -> None:
    """Vincula la serie compartida con la chequera usando la cuenta como contexto."""
    if not bank_account.default_naming_series_id or not bank_account.default_external_counter_id:
        return

    condition_json = json.dumps({"bank_account_id": bank_account.id}, sort_keys=True)
    existing = database.session.execute(
        database.select(SeriesExternalCounterMap).filter_by(
            naming_series_id=bank_account.default_naming_series_id,
            external_counter_id=bank_account.default_external_counter_id,
            condition_json=condition_json,
        )
    ).scalar_one_or_none()
    if existing:
        return

    database.session.add(
        SeriesExternalCounterMap(
            naming_series_id=bank_account.default_naming_series_id,
            external_counter_id=bank_account.default_external_counter_id,
            priority=0,
            condition_json=condition_json,
        )
    )


def _payment_numbering_defaults(bank_account_id: str | None) -> tuple[str | None, str | None]:
    """Devuelve serie y chequera predeterminadas de la cuenta bancaria."""
    if not bank_account_id:
        return None, None

    bank_account = database.session.get(BankAccount, bank_account_id)
    if not bank_account:
        return None, None

    return bank_account.default_naming_series_id, bank_account.default_external_counter_id


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


@bancos.route("/payment/debit-note/list")
@modulo_activo("cash")
@login_required
def bancos_nota_debito_lista():
    """Listado de notas de débito bancario (retiros)."""
    consulta = database.paginate(
        database.select(PaymentEntry).filter_by(payment_type="debit_note"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Notas de Débito Bancario - " + APPNAME
    return render_template(
        "bancos/pago_lista.html",
        consulta=consulta,
        titulo=titulo,
        page_heading=_("Listado de Notas de Débito Bancario"),
        new_url=url_for("bancos.bancos_nota_debito_nueva"),
    )


@bancos.route("/payment/credit-note/list")
@modulo_activo("cash")
@login_required
def bancos_nota_credito_lista():
    """Listado de notas de crédito bancario (depósitos)."""
    consulta = database.paginate(
        database.select(PaymentEntry).filter_by(payment_type="credit_note"),
        page=request.args.get("page", default=1, type=int),
        max_per_page=10,
        count=True,
    )
    titulo = "Listado de Notas de Crédito Bancario - " + APPNAME
    return render_template(
        "bancos/pago_lista.html",
        consulta=consulta,
        titulo=titulo,
        page_heading=_("Listado de Notas de Crédito Bancario"),
        new_url=url_for("bancos.bancos_nota_credito_nueva"),
    )


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
    return render_template(BANCOS_TRANSACCION_LISTA_HTML, consulta=consulta, titulo=titulo)


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


@bancos.route("/payment/debit-note/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_nota_debito_nueva():
    """Formulario de nota de débito bancaria (utiliza PaymentEntry)."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    if request.method == "POST":
        return bancos_pago_nuevo()

    return render_template(
        "bancos/nota_nueva.html",
        titulo=_("Nueva Nota de Débito Bancario") + " - " + APPNAME,
        payment_type="debit_note",
        companies=obtener_lista_entidades_por_id_razonsocial(),
    )


@bancos.route("/payment/credit-note/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_nota_credito_nueva():
    """Formulario de nota de crédito bancaria (utiliza PaymentEntry)."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    if request.method == "POST":
        return bancos_pago_nuevo()

    return render_template(
        "bancos/nota_nueva.html",
        titulo=_("Nueva Nota de Crédito Bancario") + " - " + APPNAME,
        payment_type="credit_note",
        companies=obtener_lista_entidades_por_id_razonsocial(),
    )


@bancos.route("/payment/transfer/new", methods=["GET", "POST"])
@modulo_activo("cash")
@login_required
def bancos_transferencia_nueva():
    """Formulario de transferencia entre cuentas bancarias."""
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial

    if request.method == "POST":
        return bancos_pago_nuevo()

    return render_template(
        "bancos/transferencia_nueva.html",
        titulo=_("Nueva Transferencia Bancaria") + " - " + APPNAME,
        payment_type="internal_transfer",
        companies=obtener_lista_entidades_por_id_razonsocial(),
    )


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
        gl_account_id = request.form.get("gl_account_id") or None
        company = request.form.get("company")
        default_naming_series_id = request.form.get("default_naming_series_id") or None
        default_external_counter_id = request.form.get("default_external_counter_id") or None
        if gl_account_id:
            gl_account = database.session.get(Accounts, gl_account_id)
            if not gl_account or gl_account.entity != company or gl_account.account_type != "bank":
                flash(_("Seleccione una cuenta contable de tipo banco para la compañía indicada."), "danger")
                return render_template(BANCOS_BANCO_CUENTA_NUEVO_HTML, form=formulario, titulo=titulo)
        try:
            default_naming_series_id, default_external_counter_id = _validate_bank_account_numbering_defaults(
                company=company,
                naming_series_id=default_naming_series_id,
                external_counter_id=default_external_counter_id,
            )
        except IdentifierConfigurationError as exc:
            flash(_(str(exc)), "danger")
            return render_template(BANCOS_BANCO_CUENTA_NUEVO_HTML, form=formulario, titulo=titulo)
        cuenta = BankAccount(
            bank_id=request.form.get("bank_id"),
            company=company,
            account_name=request.form.get("account_name"),
            account_no=request.form.get("account_no"),
            iban=request.form.get("iban"),
            currency=request.form.get("currency") or None,
            gl_account_id=gl_account_id,
            default_naming_series_id=default_naming_series_id,
            default_external_counter_id=default_external_counter_id,
        )
        database.session.add(cuenta)
        database.session.flush()
        _ensure_bank_account_counter_mapping(cuenta)
        database.session.commit()
        return redirect("/cash_management/bank-account/list")
    return render_template(BANCOS_BANCO_CUENTA_NUEVO_HTML, form=formulario, titulo=titulo)


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


def _save_payment_references(payment: PaymentEntry, lines: list[dict] | None = None) -> Decimal:
    """Guarda referencias de pago y actualiza saldos vivos de facturas."""
    if lines is None:
        lines = []
        i = 0
        while request.form.get(f"reference_id_{i}"):
            lines.append(
                {
                    "reference_type": request.form.get(f"reference_type_{i}", ""),
                    "reference_id": request.form.get(f"reference_id_{i}", ""),
                    "allocated_amount": _form_decimal(f"allocated_amount_{i}", "0"),
                }
            )
            i += 1

    total_allocated = Decimal("0")
    processed_reference_keys: set[tuple[str, str]] = set()
    for line in lines:
        reference_type = line.get("reference_type", "")
        reference_id = line.get("reference_id", "")
        allocated = Decimal(str(line.get("allocated_amount", "0")))
        reference_key = (reference_type, reference_id)
        if reference_key in processed_reference_keys:
            from werkzeug.exceptions import Conflict

            raise Conflict(_("No se puede aplicar la misma factura dos veces en un pago."))
        processed_reference_keys.add(reference_key)
        if allocated <= 0:
            if allocated < 0:
                from werkzeug.exceptions import Conflict

                raise Conflict(_("El monto asignado no puede ser negativo."))
            continue
        if reference_type == "purchase_invoice":
            invoice = database.session.get(PurchaseInvoice, reference_id)
        elif reference_type == "sales_invoice":
            invoice = database.session.get(SalesInvoice, reference_id)
        else:
            raise ValueError(_("Tipo de referencia inválido."))
        if not invoice:
            raise ValueError(_("Documento referenciado no existe."))
        invoice = cast(PurchaseInvoice | SalesInvoice, invoice)
        if payment.company and invoice.company and payment.company != invoice.company:
            from werkzeug.exceptions import Conflict

            raise Conflict(_("El documento referenciado no pertenece a la misma compañía."))
        outstanding = compute_outstanding_amount(invoice)
        if allocated > outstanding + Decimal("0.01"):
            raise ValueError(_("El monto aplicado no puede ser mayor al saldo pendiente."))
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
        database.session.flush()
        create_document_relation(
            source_type=reference_type,
            source_id=reference_id,
            source_item_id=None,
            target_type="payment_entry",
            target_id=payment.id,
            target_item_id=reference.id,
            qty=Decimal("1"),
            uom=None,
            rate=allocated,
            amount=allocated,
        )
        invoice.outstanding_amount = outstanding - allocated
        invoice.base_outstanding_amount = invoice.outstanding_amount
        total_allocated += allocated
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
    from cacao_accounting.contabilidad.auxiliares import obtener_lista_entidades_por_id_razonsocial
    from cacao_accounting.form_preferences import get_column_preferences

    if request.method == "POST":
        payload_raw = request.form.get("payment_payload")
        if payload_raw:
            payload = json.loads(payload_raw)
        else:
            # Fallback para pruebas unitarias que no envían payment_payload
            payload = {
                "payment_type": request.form.get("payment_type"),
                "company": request.form.get("company"),
                "bank_account_id": request.form.get("bank_account_id"),
                "posting_date": request.form.get("posting_date"),
                "paid_amount": request.form.get("paid_amount") or request.form.get("received_amount"),
                "party_id": request.form.get("party_id"),
                "party_type": request.form.get("party_type"),
                "naming_series_id": request.form.get("naming_series"),
                "external_counter_id": request.form.get("external_counter_id"),
                "external_number": request.form.get("external_number"),
            }
        try:
            payment_type = payload.get("payment_type") or "receive"
            company = payload.get("company")
            bank_account_id = payload.get("bank_account_id")
            amount = Decimal(str(payload.get("paid_amount") or "0"))
            target_bank_account_id = payload.get("target_bank_account_id")

            paid_from_account_id = payload.get("paid_from_account_id")
            paid_to_account_id = payload.get("paid_to_account_id")
            if payment_type == "internal_transfer":
                source_bank = database.session.get(BankAccount, bank_account_id) if bank_account_id else None
                target_bank = database.session.get(BankAccount, target_bank_account_id) if target_bank_account_id else None
                if source_bank and not paid_from_account_id:
                    paid_from_account_id = source_bank.gl_account_id
                if target_bank and not paid_to_account_id:
                    paid_to_account_id = target_bank.gl_account_id

            payment = PaymentEntry(
                payment_type=payment_type,
                company=company,
                bank_account_id=bank_account_id,
                party_type=payload.get("party_type"),
                party_id=payload.get("party_id"),
                paid_from_account_id=paid_from_account_id,
                paid_to_account_id=paid_to_account_id,
                remarks=payload.get("remarks"),
                docstatus=0,
            )

            if payment_type in ("pay", "debit_note", "internal_transfer"):
                payment.paid_amount = amount
                payment.base_paid_amount = amount
            if payment_type in ("receive", "credit_note", "internal_transfer"):
                payment.received_amount = amount
                payment.base_received_amount = amount

            database.session.add(payment)
            database.session.flush()

            default_series_id, default_counter_id = _payment_numbering_defaults(payment.bank_account_id)
            naming_series_id = payload.get("naming_series_id") or default_series_id
            external_counter_id = payload.get("external_counter_id") or default_counter_id

            ext_context = {
                "payment_type": payment_type,
                "bank_account_id": payment.bank_account_id,
            }
            assign_document_identifier(
                document=payment,
                entity_type="payment_entry",
                posting_date_raw=payload.get("posting_date"),
                naming_series_id=naming_series_id,
                external_counter_id=external_counter_id,
                external_number=payload.get("external_number") or None,
                external_context=ext_context,
            )

            lines = payload.get("lines") or []
            allocated = _save_payment_references(payment, lines)

            if allocated and amount != allocated and payment_type in ("pay", "receive"):
                raise ValueError(_("El monto del pago debe coincidir con el monto asignado a referencias."))

            database.session.commit()
            flash(_("Pago registrado correctamente."), "success")
            return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment.id))
        except (IdentifierConfigurationError, ValueError) as exc:
            database.session.rollback()
            flash(str(exc), "danger")

    from_purchase_invoice_ids = request.values.getlist("from_purchase_invoice")
    from_sales_invoice_ids = request.values.getlist("from_sales_invoice")
    facturas_origen = _payment_source_rows(from_purchase_invoice_ids, from_sales_invoice_ids)

    initial_payment = {}
    if facturas_origen:
        first = facturas_origen[0]["document"]
        initial_payment = {
            "company": first.company,
            "party_id": getattr(first, "supplier_id", None) or getattr(first, "customer_id", None),
            "party_type": "supplier" if facturas_origen[0]["reference_type"] == "purchase_invoice" else "customer",
            "payment_type": "pay" if facturas_origen[0]["reference_type"] == "purchase_invoice" else "receive",
            "paid_amount": float(sum((compute_outstanding_amount(row["document"]) for row in facturas_origen), Decimal("0"))),
            "lines": [
                {
                    "reference_type": row["reference_type"],
                    "reference_id": row["document"].id,
                    "document_no": row["document"].document_no or row["document"].id,
                    "total_amount": float(row["document"].grand_total or 0),
                    "outstanding_amount": float(compute_outstanding_amount(row["document"])),
                    "allocated_amount": float(compute_outstanding_amount(row["document"])),
                }
                for row in facturas_origen
            ],
        }

    transaction_config = {
        "columns": get_column_preferences(getattr(current_user, "id", None), "banking.payment_entry"),
    }

    return render_template(
        "bancos/pago_nuevo.html",
        titulo="Nuevo Pago - " + APPNAME,
        initial_payment=initial_payment,
        transaction_config=transaction_config,
        companies=obtener_lista_entidades_por_id_razonsocial(),
    )


@bancos.route("/payment/<payment_id>")
@modulo_activo("cash")
@login_required
def bancos_pago(payment_id):
    """Detalle de pago."""
    from flask import abort
    from cacao_accounting.gl.service import obtener_entradas_libro_mayor

    registro = database.session.get(PaymentEntry, payment_id)
    if not registro:
        abort(404)

    # Entradas contables
    lineas_gl = obtener_entradas_libro_mayor(voucher_type="payment_entry", voucher_id=payment_id)

    # Referencias (facturas aplicadas)
    referencias = database.session.execute(database.select(PaymentReference).filter_by(payment_id=payment_id)).scalars().all()

    # Nombres para mostrar
    banco = database.session.get(BankAccount, registro.bank_account_id) if registro.bank_account_id else None
    banco_destino = None
    if registro.payment_type == "internal_transfer" and registro.paid_to_account_id:
        banco_destino = (
            database.session.execute(
                database.select(BankAccount).filter_by(company=registro.company, gl_account_id=registro.paid_to_account_id)
            )
            .scalars()
            .first()
        )

    creador = database.session.get(User, registro.created_by) if registro.created_by else None

    titulo = (registro.document_no or payment_id) + " - " + APPNAME
    return render_template(
        "bancos/pago.html",
        registro=registro,
        titulo=titulo,
        lineas_gl=lineas_gl,
        referencias=referencias,
        banco=banco,
        banco_destino=banco_destino,
        creador=creador,
    )


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
        return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment_id))
    flash(_("Pago aprobado y contabilizado."), "success")
    return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment_id))


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
        revert_relations_for_target("payment_entry", registro.id, reason="payment_cancelled")
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
        return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment_id))
    flash(_("Pago cancelado con reverso contable."), "warning")
    return redirect(url_for(BANCOS_BANCOS_PAGO, payment_id=payment_id))
