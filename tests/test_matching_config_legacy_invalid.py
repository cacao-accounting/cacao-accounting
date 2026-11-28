# SPDX-License-Identifier: Apache-2.0
"""#1568: permite corregir configuracion legacy invalida sin bloquear por normalizacion previa."""

from __future__ import annotations

from decimal import Decimal

import pytest

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


def test_cloud_legacy_invalid_se_propone_y_aprueba(entorno_contable_aislado):
    """Cloud convierte un valor legacy inválido en propuesta auditable y la aprueba."""
    from cacao_accounting.control_review_service import approve_review
    from cacao_accounting.database import CacaoConfig, User, UserCompanyAccess

    app = entorno_contable_aislado.app
    previous = app.config.get("MODO_ESCRITORIO")
    app.config["MODO_ESCRITORIO"] = False
    try:
        with app.app_context():
            company = "cacao"
            for key in (
                "approval_engine_enabled_cacao",
                "approval_require_different_approver_cacao",
            ):
                database.session.add(CacaoConfig(key=key, value="1"))
            cfg = database.session.execute(
                database.select(PurchaseMatchingConfig).filter_by(company=company)
            ).scalar_one_or_none()
            if cfg is None:
                cfg = PurchaseMatchingConfig(company=company)
                database.session.add(cfg)
                database.session.flush()
            cfg.price_tolerance_value = Decimal("Infinity")
            database.session.commit()
            cfg_id = cfg.id
            admin_id = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one().id

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
            propuesta = update_matching_config("purchase", company, values, actor_id=str(admin_id))
            assert propuesta is not None
            assert propuesta.document_type == "config_change"
            assert propuesta.status == "Pending Approval"
            assert propuesta.review_payload["before"]["price_tolerance_value"] == "Infinity"
            assert Decimal(str(propuesta.review_payload["after"]["price_tolerance_value"])) == Decimal("5")

            # Un valor nuevo inválido sigue rechazándose en la frontera compartida.
            malos = {**values, "price_tolerance_value": "Infinity"}
            with pytest.raises(ValueError):
                update_matching_config("purchase", company, malos, actor_id=str(admin_id))

            revisor = User(
                id="revisor-1568",
                user="revisor1568",
                name="Revisor independiente",
                password=b"x",
                classification="admin",
                active=True,
                company=company,
            )
            database.session.add(revisor)
            database.session.add(UserCompanyAccess(user_id=revisor.id, company_code=company))
            database.session.commit()
            approve_review(propuesta, revisor)
            database.session.commit()
            database.session.expire_all()
            actualizado = database.session.execute(
                database.select(PurchaseMatchingConfig).filter_by(id=cfg_id).execution_options(populate_existing=True)
            ).scalar_one_or_none()
            assert actualizado is not None
            assert actualizado.price_tolerance_value == Decimal("5.0000")
    finally:
        app.config["MODO_ESCRITORIO"] = previous
