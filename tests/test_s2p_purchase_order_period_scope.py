# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2142: las OC conservan el alcance combinado Compras + Inventario.

El listado autoriza ambos módulos. El selector y el filtro de período deben
usar la unión de compañías, rechazar un rango ambiguo y no limitarse en
silencio a la compañía del primer módulo.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cacao_accounting import list_filters
from cacao_accounting.compras import services
from cacao_accounting.database import Modules, PurchaseOrder, User, database


class _FakePermisos:
    """Permisos con compañías distintas por módulo para el escenario."""

    mapping: dict[str, list[str]] = {}

    def __init__(self, modulo=None, usuario=None, libro=None):
        self.consultar = bool(self.mapping.get(str(modulo)))
        self.administrador = False
        self._companies = list(self.mapping.get(str(modulo), []))

    def obtener_companias_autorizadas(self):
        """Devuelve las compañías simuladas del módulo."""
        return self._companies


def _module_ids(app) -> tuple[str, str]:
    """Resuelve los IDs reales de los módulos usados por el helper."""
    with app.app_context():
        purchases = database.session.execute(database.select(Modules.id).filter_by(module="purchases")).scalar_one()
        inventory = database.session.execute(database.select(Modules.id).filter_by(module="inventory")).scalar_one()
    return str(purchases), str(inventory)


def test_selector_une_companias_de_compras_e_inventario(app, monkeypatch):
    """El selector muestra la unión, no solo el alcance de Compras."""
    calls: list[str] = []

    def fake_choices(module, *, current_user):
        calls.append(module)
        if module == "purchases":
            return [("", "Todas"), ("alpha", "Alfa")]
        return [("", "Todas"), ("beta", "Beta")]

    monkeypatch.setattr(list_filters, "company_choices_for_module", fake_choices)
    with app.app_context():
        choices = list_filters.company_choices_for_modules(
            ("purchases", "inventory"),
            current_user=SimpleNamespace(id="user-1"),
        )

    assert calls == ["purchases", "inventory"]
    assert [code for code, _name in choices] == ["", "alpha", "beta"]


def test_rango_ambiguo_sin_compania_responde_400(app, entorno_contable, monkeypatch):
    """Compras→Alfa e Inventario→Beta no eligen una compañía en silencio."""
    purchases_id, inventory_id = _module_ids(app)
    _FakePermisos.mapping = {purchases_id: ["alpha"], inventory_id: ["beta"]}
    monkeypatch.setattr("cacao_accounting.auth.permisos.Permisos", _FakePermisos)
    with app.app_context():
        user = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        user.classification = "user"
        database.session.commit()
        user_id = user.id

    with app.test_request_context("/buying/purchase-order/list?accounting_period_from=P2026-01"):
        from flask_login import login_user

        user = database.session.get(User, user_id)
        login_user(user)
        assert list_filters.period_company_from_request(("purchases", "inventory"), current_user=user) is None
        with pytest.raises(Exception) as error:
            list_filters.require_period_company(("purchases", "inventory"), current_user=user)
        assert getattr(error.value, "code", None) == 400


def test_consulta_se_limita_a_la_compania_autorizada_por_inventario(app, entorno_contable, monkeypatch):
    """Con acceso solo de Inventario a Beta, la consulta no incluye Alfa."""
    purchases_id, inventory_id = _module_ids(app)
    _FakePermisos.mapping = {purchases_id: [], inventory_id: ["beta"]}
    monkeypatch.setattr(services, "Permisos", _FakePermisos)
    monkeypatch.setattr(services, "is_desktop_mode", lambda: True)
    with app.app_context():
        user = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        user.classification = "user"
        database.session.commit()
        user_id = user.id

    with app.test_request_context("/buying/purchase-order/list"):
        from flask_login import login_user

        login_user(database.session.get(User, user_id))
        query = services._apply_company_scope(
            database.select(PurchaseOrder),
            PurchaseOrder,
            ("purchases", "inventory"),
        )

    compiled = query.compile()
    params = " ".join(str(value) for value in compiled.params.values())
    assert "beta" in params
    assert "alpha" not in params
