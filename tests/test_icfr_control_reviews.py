# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Independent review proposals must have no financial effect before approval."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from tests import test_bank_reconciliation_retroactive_date as bank_tests
from cacao_accounting import control_review_service as review
from cacao_accounting.database import (
    AccountingPeriod,
    ApprovalAction,
    ApprovalRequest,
    AuditTrail,
    CacaoConfig,
    PeriodCloseCheck,
    PeriodCloseRun,
    Reconciliation,
    ReconciliationItem,
    User,
    database,
)

COMPANY = bank_tests.COMPANY
OPEN_PERIOD_START = bank_tests.OPEN_PERIOD_START
app_ctx = bank_tests.app_ctx
chart = bank_tests.chart
_bank_transaction = bank_tests._bank_transaction
_gl_entry_target = bank_tests._gl_entry_target


@pytest.fixture()
def reviewers(app_ctx):
    """Enable independent Cloud review with two separately identified administrators."""
    app_ctx.config["MODO_ESCRITORIO"] = False
    app_ctx.config["INTERNAL_CONTROLS_ENFORCE"] = True
    from cacao_accounting.database import Modules

    database.session.add(Modules(module="accounting", default=True, enabled=True))
    reviewer = User(id="reviewer", user="reviewer", name="Reviewer", password=b"x", classification="admin", active=True)
    database.session.add(reviewer)
    for key in ("approval_engine_enabled_", "approval_require_different_approver_"):
        database.session.add(CacaoConfig(key=key + COMPANY, value="1"))
    database.session.commit()
    with app_ctx.test_request_context():
        yield database.session.get(User, "admin"), reviewer


def _bank_request(chart):
    """Build a valid bank allocation against an immutable posted GL entry."""
    from cacao_accounting.bancos.reconciliation_service import BankReconciliationMatch, BankReconciliationRequest

    transaction = _bank_transaction(chart, deposit=Decimal("100"))
    target = _gl_entry_target(chart, "ICFR-1", Decimal("100"))
    return transaction, BankReconciliationRequest(
        COMPANY, OPEN_PERIOD_START, [BankReconciliationMatch(transaction.id, "gl_entry", target, Decimal("100"))]
    )


def test_bank_proposal_does_not_allocate_and_independent_admin_executes(chart, reviewers):
    """Self approval and ordinary direct calls cannot execute a pending reconciliation."""
    from cacao_accounting.bancos.reconciliation_service import reconcile_bank_items

    preparer, reviewer = reviewers
    transaction, request = _bank_request(chart)
    pending = reconcile_bank_items(request, actor_id=preparer.id)
    database.session.commit()
    assert isinstance(pending, ApprovalRequest)
    assert not transaction.is_reconciled
    assert database.session.query(ReconciliationItem).count() == 0
    assert not review.review_is_allowed(pending, preparer)
    with pytest.raises(ValueError):
        review.approve_review(pending, preparer)
    assert reconcile_bank_items(request, actor_id=reviewer.id).id == pending.id
    result = review.approve_review(pending, reviewer, "Verified")
    database.session.commit()
    assert isinstance(result, Reconciliation)
    assert transaction.is_reconciled
    assert database.session.query(ReconciliationItem).count() == 1
    assert pending.status == "Approved"
    assert database.session.query(ApprovalAction).one().approved_by == reviewer.id
    evidence = database.session.query(AuditTrail).filter_by(source_module="control_review").all()
    assert {event.actor_user_id for event in evidence} == {preparer.id, reviewer.id}
    with pytest.raises(ValueError):
        review.approve_review(pending, reviewer)


def test_bank_pending_survives_toggle_and_reject_has_no_effect(chart, reviewers):
    """Turning off configuration cannot bypass an already required independent review."""
    from cacao_accounting.bancos.reconciliation_service import reconcile_bank_items

    preparer, reviewer = reviewers
    transaction, request = _bank_request(chart)
    pending = reconcile_bank_items(request, actor_id=preparer.id)
    database.session.query(CacaoConfig).filter_by(key="approval_engine_enabled_" + COMPANY).one().value = "0"
    assert reconcile_bank_items(request, actor_id=preparer.id).id == pending.id
    info = review.review_pending_info(pending, reviewer)
    assert info["requester_name"] == preparer.name
    assert review.review_pending_info(pending, preparer) is None
    review.reject_review(pending, reviewer)
    database.session.commit()
    assert not transaction.is_reconciled
    assert database.session.query(Reconciliation).count() == 0
    assert pending.status == "Rejected"
    with pytest.raises(ValueError):
        review.reject_review(pending, reviewer)


def test_review_execution_and_difference_share_the_caller_transaction(chart, reviewers, monkeypatch):
    """No allocation or difference survives if the approval transaction is rolled back."""
    from cacao_accounting.bancos import services
    from cacao_accounting.bancos.reconciliation_service import reconcile_bank_items

    preparer, reviewer = reviewers
    transaction, request = _bank_request(chart)
    applied = []
    monkeypatch.setattr(services, "_post_bank_difference_adjustment", lambda *args, **kw: applied.append(args))
    pending = reconcile_bank_items(request, actor_id=preparer.id, differences=[(transaction.id, Decimal("1"))])
    database.session.commit()
    assert applied == []
    review.approve_review(pending, reviewer)
    assert len(applied) == 1
    database.session.rollback()
    assert not transaction.is_reconciled
    assert pending.status == "Pending Approval"
    assert database.session.query(ReconciliationItem).count() == 0
    assert database.session.query(ApprovalAction).count() == 0


def test_bank_review_revalidates_closed_period(chart, reviewers):
    """A period closed while review is pending cannot receive the reviewed reconciliation."""
    from cacao_accounting.bancos.reconciliation_service import BankReconciliationError, reconcile_bank_items

    preparer, reviewer = reviewers
    transaction, request = _bank_request(chart)
    pending = reconcile_bank_items(request, actor_id=preparer.id)
    period = database.session.query(AccountingPeriod).filter_by(entity=COMPANY, is_closed=False).one()
    period.is_closed = True
    database.session.commit()
    with pytest.raises(BankReconciliationError, match="cerrado"):
        review.approve_review(pending, reviewer)
    assert not transaction.is_reconciled
    assert pending.status == "Pending Approval"


def test_changed_proposal_invalidates_old_request(chart, reviewers):
    """A changed financial proposal gets a fresh review and cannot reuse previous approval."""
    preparer, _ = reviewers
    first = review.require_review("monthly_close", "run", COMPANY, preparer.id, {"value": "100"})
    second = review.require_review("monthly_close", "run", COMPANY, preparer.id, {"value": "200"})
    assert first.status == "Invalidated"
    assert first.id != second.id


@pytest.mark.parametrize("actor_id", [None, "missing"])
def test_preparation_requires_identified_authorized_actor(chart, reviewers, actor_id):
    """Direct service calls cannot create proposals anonymously."""
    with pytest.raises(ValueError, match="autorización"):
        review.require_review("monthly_close", "run", COMPANY, actor_id, {})


def test_unclassified_preparer_fails_closed(chart, reviewers):
    """Missing role ranks cannot silently lower the preparation hierarchy."""
    preparer, _ = reviewers
    user = User(id="ordinary", user="ordinary", name="Ordinary", password=b"x", classification="user", active=True)
    database.session.add(user)
    database.session.flush()
    with pytest.raises(ValueError, match="nivel"):
        review.require_review("monthly_close", "run", COMPANY, preparer.id, {}, (user.id,))


def _monthly_run():
    """Persist successful prerequisite checks for a monthly close proposal."""
    from cacao_accounting.contabilidad.services import REQUIRED_MONTHLY_CLOSE_CHECKS

    period = database.session.query(AccountingPeriod).filter_by(entity=COMPANY, is_closed=False).one()
    run = PeriodCloseRun(company=COMPANY, period_id=period.id, run_status="open", created_by="admin")
    database.session.add(run)
    database.session.flush()
    for kind in REQUIRED_MONTHLY_CLOSE_CHECKS:
        database.session.add(PeriodCloseCheck(close_run_id=run.id, check_type=kind, check_status="passed"))
    database.session.commit()
    return period, run


def test_monthly_close_and_reopen_remain_pending_until_independent_review(chart, reviewers, monkeypatch):
    """Both operations use the ordinary validators and defer their effects until approved."""
    from cacao_accounting.contabilidad import services

    preparer, reviewer = reviewers
    period, run = _monthly_run()
    monkeypatch.setattr(services, "_record_monthly_integrity_checks", lambda *_: None)
    pending = services.finalize_monthly_close(run.id, preparer.id)
    assert not period.is_closed
    assert run.run_status == "open"
    assert review.review_pending_info(pending, reviewer)["label"]
    review.approve_review(pending, reviewer)
    database.session.commit()
    assert period.is_closed
    assert run.closed_by == reviewer.id
    pending = services.reopen_accounting_period(period.id, preparer.id, "Corrección autorizada")
    assert period.is_closed
    assert review.review_pending_info(pending, reviewer)["label"]
    review.approve_review(pending, reviewer)
    database.session.commit()
    assert not period.is_closed
    assert run.run_status == "open"


def test_changed_ledger_blocks_review_and_restores_execution_context(chart, reviewers, monkeypatch):
    """Approval failure cannot leak execution authority into later service calls."""
    from cacao_accounting.contabilidad import services

    preparer, reviewer = reviewers
    period, run = _monthly_run()
    monkeypatch.setattr(services, "_record_monthly_integrity_checks", lambda *_: None)
    pending = services.finalize_monthly_close(run.id, preparer.id)
    _gl_entry_target(chart, "ICFR-CHANGED", Decimal("20"))
    with pytest.raises(ValueError, match="cambió"):
        review.approve_review(pending, reviewer)
    assert review._execution.get() is None
    assert not period.is_closed
    assert pending.status == "Pending Approval"


def test_review_execution_cannot_authorize_another_operation(chart, reviewers):
    """A review capability is restricted to one operation and company."""
    preparer, _ = reviewers
    pending = review.require_review("monthly_close", "run", COMPANY, preparer.id, {})
    token = review._execution.set(pending)
    try:
        with pytest.raises(ValueError, match="corresponde"):
            review.require_review("period_reopen", "run", COMPANY, preparer.id, {})
    finally:
        review._execution.reset(token)


def test_desktop_and_disabled_reviews_preserve_existing_behavior(chart, reviewers):
    """Optional review adds no operational obligation when disabled or on Desktop."""
    from flask import current_app

    current_app.config["MODO_ESCRITORIO"] = True
    assert review.require_review("monthly_close", "run", COMPANY, None, {}) is None
    assert review.period_review_payload(
        SimpleNamespace(id="period", entity=COMPANY, start=date(2025, 1, 1), end=date(2025, 1, 31), is_closed=False)
    )["ledger_hash"]


def test_rbac_remains_mandatory_when_independent_review_is_disabled(chart, reviewers):
    """The optional approval switch never disables backend authorization."""
    preparer, _ = reviewers
    database.session.query(CacaoConfig).filter_by(key="approval_require_different_approver_" + COMPANY).one().value = "0"
    with pytest.raises(ValueError, match="autorización"):
        review.require_review("monthly_close", "run", COMPANY, None, {})
    assert review.require_review("monthly_close", "run", COMPANY, preparer.id, {}) is None


def test_derived_journal_execution_is_limited_to_the_reviewed_difference(chart, reviewers):
    """Only the approved bank amount and company may authorize the derived accounting journal."""
    from cacao_accounting.database import ComprobanteContable

    preparer, reviewer = reviewers
    journal = ComprobanteContable(id="difference", entity=COMPANY)
    with review.reviewed_bank_difference(journal, "transaction", Decimal("1"), reviewer.id):
        assert review._execution.get() is None
    pending = review.require_review(
        "bank_reconciliation", "transaction", COMPANY, preparer.id, {"differences": [["transaction", "1"]]}
    )
    token = review._execution.set(pending)
    try:
        with review.reviewed_bank_difference(journal, "transaction", Decimal("-1"), reviewer.id):
            pass
        with pytest.raises(ValueError, match="corresponde"):
            with review.reviewed_bank_difference(journal, "transaction", Decimal("2"), reviewer.id):
                pytest.fail("Unreviewed amount was allowed")
    finally:
        review._execution.reset(token)


def _matching_values(**overrides):
    """Complete purchase-matching form with non-weakening defaults."""
    values = {
        "matching_type": "3-way",
        "price_tolerance_type": "percentage",
        "price_tolerance_value": Decimal("0"),
        "qty_tolerance_type": "percentage",
        "qty_tolerance_value": Decimal("0"),
        "require_purchase_order": True,
        "bridge_account_required": True,
        "auto_reconcile": True,
        "allow_price_difference": False,
    }
    values.update(overrides)
    return values


def _weakening_config_review(chart, config_reviewers, overrides):
    """Create a weakening purchase-matching change and keep the config untouched."""
    from cacao_accounting.database import ApprovalRequest, PurchaseMatchingConfig, PurchaseReconciliation
    from cacao_accounting.matching_config_service import update_matching_config

    preparer, reviewer = config_reviewers
    database.session.add(PurchaseMatchingConfig(company=COMPANY))
    database.session.add(
        PurchaseReconciliation(
            company=COMPANY,
            matching_type="3-way",
            purchase_invoice_id="pinv-snapshot",
            price_tolerance_type="percentage",
            price_tolerance_value=Decimal("0"),
            qty_tolerance_type="percentage",
            qty_tolerance_value=Decimal("0"),
            matched_amount=Decimal("10"),
            matched_date=date.today(),
            status="reconciled",
        )
    )
    database.session.commit()

    pending = update_matching_config("purchase", COMPANY, _matching_values(**overrides), actor_id=preparer.id)
    database.session.commit()
    assert isinstance(pending, ApprovalRequest)
    assert pending.status == "Pending Approval"
    config = database.session.execute(database.select(PurchaseMatchingConfig).filter_by(company=COMPANY)).scalar_one()
    assert config.matching_type == "3-way"
    assert config.auto_reconcile is True
    assert not review.review_is_allowed(pending, preparer)
    with pytest.raises(ValueError):
        review.approve_review(pending, preparer)
    return pending, config, reviewer


@pytest.fixture()
def config_reviewers(reviewers):
    """Enable the admin module so config_change authorization resolves."""
    from cacao_accounting.database import Modules

    database.session.add(Modules(module="admin", default=True, enabled=True))
    database.session.commit()
    return reviewers


def test_weakening_config_change_waits_for_independent_review(chart, config_reviewers):
    """A 3-way to 2-way switch requires another administrator before it lands."""
    from cacao_accounting.database import AuditTrail

    pending, config, reviewer = _weakening_config_review(chart, config_reviewers, {"matching_type": "2-way"})
    result = review.approve_review(pending, reviewer, "Reviewed")
    database.session.commit()
    assert config.matching_type == "2-way"
    assert isinstance(result, type(config))
    evidence = database.session.query(AuditTrail).filter_by(source_module="control_review").all()
    assert {event.actor_user_id for event in evidence} == {"admin", "reviewer"}


def test_reconciliation_keeps_the_snapshot_when_config_changes(chart, config_reviewers):
    """Historical matching snapshots are never rewritten by later config edits."""
    from cacao_accounting.database import PurchaseReconciliation

    pending, config, reviewer = _weakening_config_review(chart, config_reviewers, {"price_tolerance_value": Decimal("5")})
    review.approve_review(pending, reviewer)
    database.session.commit()
    historical = database.session.execute(database.select(PurchaseReconciliation).filter_by(company=COMPANY)).scalar_one()
    assert config.price_tolerance_value == Decimal("5")
    assert historical.matching_type == "3-way"
    assert historical.price_tolerance_type == "percentage"
    assert historical.price_tolerance_value == Decimal("0")
    assert historical.qty_tolerance_value == Decimal("0")
    assert historical.matched_amount == Decimal("10")


def test_strengthening_config_change_applies_without_review(chart, config_reviewers):
    """Non-weakening edits still land immediately under an active four-eyes setup."""
    from cacao_accounting.database import ApprovalRequest, PurchaseMatchingConfig
    from cacao_accounting.matching_config_service import update_matching_config

    preparer, reviewer = config_reviewers
    database.session.add(PurchaseMatchingConfig(company=COMPANY, auto_reconcile=False))
    database.session.commit()

    result = update_matching_config("purchase", COMPANY, _matching_values(), actor_id=preparer.id)

    assert result is not None and not isinstance(result, ApprovalRequest)
    assert result.auto_reconcile is True
    assert (
        database.session.execute(
            database.select(database.func.count()).select_from(ApprovalRequest).filter_by(document_type="config_change")
        ).scalar_one()
        == 0
    )


def test_weakening_classification_matches_the_agreed_policy():
    """4-way switches, disabled guards, enabled allowances and tolerance moves."""
    from cacao_accounting.matching_config_service import weakened_fields

    purchase = _matching_values()
    assert weakened_fields("purchase", purchase, purchase) == []
    assert weakened_fields("purchase", purchase, _matching_values(matching_type="2-way")) == ["matching_type"]
    assert weakened_fields("purchase", purchase, _matching_values(allow_price_difference=True)) == ["allow_price_difference"]
    assert weakened_fields("purchase", purchase, _matching_values(require_purchase_order=False)) == ["require_purchase_order"]
    assert weakened_fields("purchase", purchase, _matching_values(auto_reconcile=False)) == ["auto_reconcile"]
    assert "price_tolerance" in weakened_fields("purchase", purchase, _matching_values(price_tolerance_value=Decimal("5")))
    assert "qty_tolerance" in weakened_fields("purchase", purchase, _matching_values(qty_tolerance_value=Decimal("5")))
    strengthening = _matching_values(require_purchase_order=False).copy()
    assert weakened_fields("purchase", strengthening, _matching_values()) == []
    sales = {
        "matching_type": "3-way",
        "price_tolerance_type": "percentage",
        "price_tolerance_value": Decimal("0"),
        "require_sales_order": True,
        "allow_price_difference": False,
    }
    assert weakened_fields("sales", sales, sales) == []
    assert weakened_fields("sales", sales, {**sales, "matching_type": "2-way"}) == ["matching_type"]
    assert weakened_fields("sales", sales, {**sales, "require_sales_order": False}) == ["require_sales_order"]
    assert weakened_fields("sales", sales, {**sales, "allow_price_difference": True}) == ["allow_price_difference"]
