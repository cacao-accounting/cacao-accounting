"""Tests for S2P-15: revert_relations_for_target should also revert downstream source relations."""

import pytest
from cacao_accounting import create_app
from cacao_accounting.database import database, DocumentRelation
from cacao_accounting.database.helpers import inicia_base_de_datos
from cacao_accounting.document_flow.service import revert_relations_for_target


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test_secret_key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        from cacao_accounting.datos.dev import master_data

        inicia_base_de_datos(app, user="cacao", passwd="cacao", with_examples=False)
        master_data()
        database.session.commit()
        yield app


def _make_relation(source_type, source_id, target_type, target_id, company="cacao"):
    rel = DocumentRelation(
        source_type=source_type,
        source_id=source_id,
        source_item_id=None,
        target_type=target_type,
        target_id=target_id,
        target_item_id=None,
        company=company,
        qty=1,
        relation_type="link",
        status="active",
    )
    database.session.add(rel)
    database.session.flush()
    return rel


def test_s2p15_target_and_source_relations_reverted(app_ctx):
    """S2P-15: cancelling receipt should revert both upstream (receipt as TARGET)
    and downstream (receipt as SOURCE) relations."""
    receipt_id = "test_receipt_001"
    order_id = "test_order_001"
    invoice_id = "test_invoice_001"

    rel_upstream = _make_relation("purchase_order", order_id, "purchase_receipt", receipt_id)
    rel_downstream = _make_relation("purchase_receipt", receipt_id, "purchase_invoice", invoice_id)

    reverted = revert_relations_for_target("purchase_receipt", receipt_id, reason="test_cancel")
    assert reverted == 2

    assert database.session.get(DocumentRelation, rel_upstream.id).status == "reverted"
    assert database.session.get(DocumentRelation, rel_downstream.id).status == "reverted"


def test_s2p15_only_target_reverted_when_no_downstream(app_ctx):
    """Normal case: only upstream relation exists, no downstream."""
    receipt_id = "test_receipt_002"
    order_id = "test_order_002"

    rel_upstream = _make_relation("purchase_order", order_id, "purchase_receipt", receipt_id)

    reverted = revert_relations_for_target("purchase_receipt", receipt_id, reason="test_cancel")
    assert reverted == 1

    assert database.session.get(DocumentRelation, rel_upstream.id).status == "reverted"
