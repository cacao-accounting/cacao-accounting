# SPDX-License-Identifier: Apache-2.0
"""#1784: capitalizaci?n multimoneda debe ser at?mica por comprobante fuente."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cacao_accounting.contabilidad import project_capitalization_service as pcs
from cacao_accounting.contabilidad.project_capitalization_service import ProjectCapitalizationService
from cacao_accounting.database import ComprobanteContable, database


class _Dummy:
    def __init__(self, id):
        self.id = id


def test_process_group_is_atomic_when_second_submit_fails(app, monkeypatch):
    with app.app_context():
        from cacao_accounting.database import Entity

        entity = database.session.execute(database.select(Entity.code).filter_by(code="cacao")).scalar_one()
        src = ComprobanteContable(
            entity=entity,
            date=__import__("datetime").date(2026, 1, 15),
            status="draft",
            book_codes='["DEFAULT_BOOK"]',
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(src)
        database.session.commit()
        src_id = src.id

        created = [_Dummy("CAP-A"), _Dummy("CAP-B")]

        def fake_create(*_args, **_kwargs):
            return created.pop(0)

        calls = {"n": 0}

        commits = []

        def fake_submit(_jid, user_id=None, commit=True):
            calls["n"] += 1
            commits.append(commit)
            if calls["n"] == 2:
                raise RuntimeError("tasa faltante")
            return []

        monkeypatch.setattr(pcs, "_create_capitalization_journal", fake_create)
        monkeypatch.setattr(pcs, "submit_journal", fake_submit)

        svc = ProjectCapitalizationService()
        line = pcs.CapitalizationLine(
            entry=type("E", (), {"account_currency": "NIO", "company_currency": "NIO"})(),
            debit_account_code="1.1",
            credit_account_code="5.1",
            value=Decimal("10"),
        )
        line2 = pcs.CapitalizationLine(
            entry=type("E", (), {"account_currency": "USD", "company_currency": "NIO"})(),
            debit_account_code="1.1",
            credit_account_code="5.1",
            value=Decimal("5"),
        )

        with pytest.raises(RuntimeError, match="tasa faltante"):
            with database.session.begin_nested():
                svc._process_group(entity, src_id, [line, line2], "admin")

        database.session.expire_all()
        src = database.session.get(ComprobanteContable, src_id)
        assert src.capitalized_by_id is None
        assert calls["n"] == 2
        assert commits == [False, False]
