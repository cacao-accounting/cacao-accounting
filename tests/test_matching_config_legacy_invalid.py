# SPDX-License-Identifier: Apache-2.0
"""#1568: permite corregir configuracion legacy invalida sin bloquear por normalizacion previa."""

from __future__ import annotations

from decimal import Decimal

from cacao_accounting.database import PurchaseMatchingConfig, database
from cacao_accounting.matching_config_service import update_matching_config


def test_update_matching_config_can_replace_legacy_invalid_tolerance(entorno_contable):
    app = entorno_contable.app
    previous = app.config.get("MODO_ESCRITORIO")
    app.config["MODO_ESCRITORIO"] = True
    try:
        with app.app_context():
            company = "cacao"
            cfg = database.session.execute(
                database.select(PurchaseMatchingConfig).filter_by(company=company)
            ).scalar_one_or_none()
            if cfg is None:
                cfg = PurchaseMatchingConfig(company=company)
                database.session.add(cfg)
                database.session.flush()

            # Simula legado inválido persistido; la corrección no debe bloquearse.
            cfg.price_tolerance_value = Decimal("Infinity")
            database.session.commit()
            cfg_id = cfg.id

            values = {
                "matching_type": cfg.matching_type or "3-way",
                "price_tolerance_type": cfg.price_tolerance_type or "percentage",
                "price_tolerance_value": "5",
                "qty_tolerance_type": cfg.qty_tolerance_type or "percentage",
                "qty_tolerance_value": str(cfg.qty_tolerance_value or 0),
                "require_purchase_order": bool(cfg.require_purchase_order),
                "bridge_account_required": bool(cfg.bridge_account_required),
                "auto_reconcile": bool(cfg.auto_reconcile),
                "allow_price_difference": bool(cfg.allow_price_difference),
            }
            result = update_matching_config("purchase", company, values, actor_id=None)
            database.session.commit()

            refreshed = database.session.get(PurchaseMatchingConfig, cfg_id)
            assert refreshed is not None
            assert refreshed.price_tolerance_value == Decimal("5.0000")
            assert result is refreshed or result is not None
    finally:
        app.config["MODO_ESCRITORIO"] = previous
