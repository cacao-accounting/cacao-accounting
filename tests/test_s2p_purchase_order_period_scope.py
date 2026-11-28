# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2142: las OC conservan el alcance combinado Compras + Inventario.

El listado autoriza ambos módulos. El selector y el filtro de período deben
usar la unión de compañías, rechazar un rango ambiguo y no limitarse en
silencio a la compañía del primer módulo.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from cacao_accounting import create_app, list_filters
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.compras import services
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Currency,
    Entity,
    FiscalYear,
    Modules,
    PurchaseOrder,
    PurchaseReceipt,
    User,
    UserCompanyAccess,
    database,
)


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


PERIODO_MAYO = "PB-2026-05"
PERIODO_ABRIL = "PB-2026-04"
CONTRASENA = "periodo-2026"


@pytest.fixture
def listado_oc_periodo():
    """App aislada con dos compañías y permisos reales por módulo."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="purchases", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                Entity(code="alfa", name="Alfa", company_name="Alfa SA", tax_id="J-A", currency="NIO", enabled=True),
                Entity(code="beta", name="Beta", company_name="Beta SA", tax_id="J-B", currency="NIO", enabled=True),
                User(
                    id="solo_inventario",
                    user="solo_inventario",
                    name="Inventario Beta",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="compras_ambas",
                    user="compras_ambas",
                    name="Compras Alfa y Beta",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="admin_beta",
                    user="admin_beta",
                    name="Administrador con Beta",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
                User(
                    id="sin_modulos",
                    user="sin_modulos",
                    name="Sin módulos ni compañías",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="solo_inventario", company_code="beta"),
                UserCompanyAccess(user_id="compras_ambas", company_code="alfa"),
                UserCompanyAccess(user_id="compras_ambas", company_code="beta"),
                UserCompanyAccess(user_id="admin_beta", company_code="beta"),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                FiscalYear(
                    id="FY-BETA-2026",
                    entity="beta",
                    name="2026",
                    year_start_date=date(2026, 1, 1),
                    year_end_date=date(2026, 12, 31),
                    is_closed=False,
                ),
                FiscalYear(
                    id="FY-ALFA-2026",
                    entity="alfa",
                    name="2026",
                    year_start_date=date(2026, 1, 1),
                    year_end_date=date(2026, 12, 31),
                    is_closed=False,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                AccountingPeriod(
                    id=PERIODO_MAYO,
                    entity="beta",
                    fiscal_year_id="FY-BETA-2026",
                    name="Mayo 2026",
                    start=date(2026, 5, 1),
                    end=date(2026, 5, 31),
                    enabled=True,
                    is_closed=False,
                ),
                AccountingPeriod(
                    id=PERIODO_ABRIL,
                    entity="beta",
                    fiscal_year_id="FY-BETA-2026",
                    name="Abril 2026",
                    start=date(2026, 4, 1),
                    end=date(2026, 4, 30),
                    enabled=True,
                    is_closed=False,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                PurchaseOrder(
                    company="beta",
                    posting_date=date(2026, 5, 12),
                    docstatus=1,
                    document_no="PO-BETA-MAYO",
                    supplier_name="Proveedor Beta Mayo",
                    grand_total=150,
                ),
                PurchaseOrder(
                    company="beta",
                    posting_date=date(2026, 4, 10),
                    docstatus=1,
                    document_no="PO-BETA-ABRIL",
                    supplier_name="Proveedor Beta Abril",
                    grand_total=250,
                ),
                PurchaseOrder(
                    company="alfa",
                    posting_date=date(2026, 5, 20),
                    docstatus=1,
                    document_no="PO-ALFA-MAYO",
                    supplier_name="Proveedor Alfa Mayo",
                    grand_total=350,
                ),
                PurchaseReceipt(
                    company="beta",
                    posting_date=date(2026, 5, 12),
                    docstatus=1,
                    document_no="PR-BETA-MAYO",
                    supplier_name="Proveedor Beta Mayo",
                    grand_total=150,
                ),
                PurchaseReceipt(
                    company="beta",
                    posting_date=date(2026, 4, 10),
                    docstatus=1,
                    document_no="PR-BETA-ABRIL",
                    supplier_name="Proveedor Beta Abril",
                    grand_total=250,
                ),
                PurchaseReceipt(
                    company="alfa",
                    posting_date=date(2026, 5, 20),
                    docstatus=1,
                    document_no="PR-ALFA-MAYO",
                    supplier_name="Proveedor Alfa Mayo",
                    grand_total=350,
                ),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("solo_inventario", "inventory_user")
        asigna_rol_a_usuario("compras_ambas", "purchasing_user")
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _login(client, usuario: str) -> None:
    """Autentica al usuario del escenario mediante el login real."""
    response = client.post(
        "/login",
        data={"usuario": usuario, "acceso": CONTRASENA},
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_listado_con_periodo_conserva_alcance_de_inventario(listado_oc_periodo):
    """Un usuario con acceso solo de Inventario a Beta ve sus OC del período."""
    client = listado_oc_periodo.test_client()
    _login(client, "solo_inventario")

    response = client.get(f"/buying/purchase-order/list?accounting_period_from={PERIODO_MAYO}")

    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_data(as_text=True)
    assert "PO-BETA-MAYO" in body
    assert "PO-BETA-ABRIL" not in body
    assert "PO-ALFA-MAYO" not in body


def test_listado_de_recepciones_conserva_alcance_de_inventario(listado_oc_periodo):
    """El filtro de período de recepciones usa el alcance de Inventario."""
    client = listado_oc_periodo.test_client()
    _login(client, "solo_inventario")

    response = client.get(f"/buying/purchase-receipt/list?accounting_period_from={PERIODO_MAYO}")

    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_data(as_text=True)
    assert "PR-BETA-MAYO" in body
    assert "PR-BETA-ABRIL" not in body
    assert "PR-ALFA-MAYO" not in body


def test_listado_rechaza_periodo_ambiguo_sin_compania(listado_oc_periodo):
    """Dos compañías autorizadas exigen compañía explícita para el período."""
    client = listado_oc_periodo.test_client()
    _login(client, "compras_ambas")

    response = client.get(f"/buying/purchase-order/list?accounting_period_from={PERIODO_MAYO}")

    assert response.status_code == 400


def test_listado_con_periodo_y_compania_explicita_acota_ordenes(listado_oc_periodo):
    """Con compañía explícita solo aparecen las OC de Beta dentro del período."""
    client = listado_oc_periodo.test_client()
    _login(client, "compras_ambas")

    response = client.get(f"/buying/purchase-order/list?company=beta&accounting_period_from={PERIODO_MAYO}")

    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_data(as_text=True)
    assert "PO-BETA-MAYO" in body
    assert "PO-BETA-ABRIL" not in body
    assert "PO-ALFA-MAYO" not in body


def test_selector_de_periodo_consulta_para_solo_inventario(listado_oc_periodo):
    """#2142: el catálogo de períodos es consultable sin permiso de Contabilidad."""
    client = listado_oc_periodo.test_client()
    _login(client, "solo_inventario")

    response = client.get("/api/search-select?doctype=accounting_period_id&company=beta&q=Mayo")

    assert response.status_code == 200, response.get_data(as_text=True)
    assert "Mayo 2026" in response.get_data(as_text=True)


def test_selector_de_periodo_rechaza_usuario_sin_alcance(listado_oc_periodo):
    """Un usuario sin módulos dueños del catálogo recibe 403, no el listado."""
    client = listado_oc_periodo.test_client()
    _login(client, "sin_modulos")

    response = client.get("/api/search-select?doctype=accounting_period_id&q=Mayo")

    assert response.status_code == 403, response.get_data(as_text=True)


def test_opciones_de_compania_del_administrador_cloud_usa_concesiones(listado_oc_periodo):
    """#2142: el administrador Cloud solo ve las compañías con concesión explícita."""
    from cacao_accounting.database import User as UserModel

    with listado_oc_periodo.app_context():
        admin = database.session.execute(database.select(UserModel).filter_by(user="admin_beta")).scalar_one()
        choices = list_filters.company_choices_for_module("purchases", current_user=admin)

    assert [code for code, _nombre in choices] == ["", "beta"]
