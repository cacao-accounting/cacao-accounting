# SPDX-License-Identifier: Apache-2.0
"""#1568: permite corregir configuracion legacy invalida sin bloquear por normalizacion previa."""

from __future__ import annotations

from decimal import Decimal

from cacao_accounting.database import PurchaseMatchingConfig, database


def test_update_matching_config_can_replace_legacy_invalid_tolerance(app):
    with app.app_context():
        company = database.session.execute(database.select(PurchaseMatchingConfig.company).limit(1)).scalar_one_or_none()
        if not company:
            company = "cacao"
        cfg = database.session.execute(database.select(PurchaseMatchingConfig).filter_by(company=company)).scalar_one_or_none()
        if cfg is None:
            cfg = PurchaseMatchingConfig(company=company)
            database.session.add(cfg)
            database.session.flush()

        # Simula legado inválido persistido; la corrección no debe bloquearse.
        cfg.price_tolerance_value = Decimal("Infinity")
        database.session.commit()

        from cacao_accounting.matching_config_service import _prepare_config_change

        values = {
            "matching_type": cfg.matching_type or "three_way",
            "price_tolerance_type": cfg.price_tolerance_type or "percentage",
            "price_tolerance_value": "5",
            "qty_tolerance_type": cfg.qty_tolerance_type or "percentage",
            "qty_tolerance_value": str(cfg.qty_tolerance_value or 0),
        }
        typed_after, payload = _prepare_config_change("purchase", cfg, values, None)
        assert typed_after["price_tolerance_value"] == Decimal("5")
        assert payload["changed_fields"]
