"""Regresiones de renderizado y acceso del formulario de costos de importación."""

from collections import Counter
from datetime import date
from html.parser import HTMLParser
import json

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    ImportLandedCost,
    ImportLandedCostCharge,
    ImportLandedCostItem,
    Item,
    Modules,
    PurchaseInvoice,
    UOM,
    User,
    UserCompanyAccess,
    database,
)


class _FormFieldParser(HTMLParser):
    """Count rendered form field IDs and submitted names."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: Counter[str] = Counter()
        self.names: Counter[str] = Counter()
        self.transaction_config: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track IDs and names from rendered form controls."""
        if tag not in {"input", "select", "textarea"}:
            attributes = dict(attrs)
            expression = attributes.get("x-data") or ""
            if expression.startswith("transactionForm(") and expression.endswith(")"):
                self.transaction_config = json.loads(expression[len("transactionForm(") : -1])
            return
        attributes = dict(attrs)
        if field_id := attributes.get("id"):
            self.ids[field_id] += 1
        if field_name := attributes.get("name"):
            self.names[field_name] += 1


def test_import_landed_cost_form_renders_company_and_date_once(authenticated_client):
    """The shared header owns company/date fields without duplicate controls."""
    client = authenticated_client("admin")

    response = client.get("/buying/import-landed-cost/new?company=alpha&posting_date=2026-10-31")

    assert response.status_code == 200
    parser = _FormFieldParser()
    parser.feed(response.get_data(as_text=True))

    for field in ("company", "posting_date"):
        assert parser.ids[field] == 1
        assert parser.names[field] == 1

    assert parser.transaction_config is not None
    assert parser.transaction_config["initialHeader"] == {"company": "alpha", "posting_date": "2026-10-31"}


def test_import_landed_cost_form_preserves_fields_after_invalid_post(authenticated_client):
    """An invalid allocation method returns the submitted company and date to the form."""
    client = authenticated_client("admin")

    response = client.post(
        "/buying/import-landed-cost/new",
        data={"company": "alpha", "posting_date": "2026-10-31", "allocation_method": "invalid"},
    )

    assert response.status_code == 200
    parser = _FormFieldParser()
    parser.feed(response.get_data(as_text=True))
    assert parser.transaction_config is not None
    assert parser.transaction_config["initialHeader"] == {"company": "alpha", "posting_date": "2026-10-31"}


def test_import_landed_cost_invalid_post_prefers_submitted_values_over_query(authenticated_client):
    """An invalid POST re-renders the submitted values, not stale URL filters."""
    client = authenticated_client("admin")

    response = client.post(
        "/buying/import-landed-cost/new?company=alpha&posting_date=2026-10-30",
        data={"company": "cacao", "posting_date": "2026-10-31", "allocation_method": "invalid"},
    )

    assert response.status_code == 200
    parser = _FormFieldParser()
    parser.feed(response.get_data(as_text=True))
    assert parser.transaction_config is not None
    assert parser.transaction_config["initialHeader"] == {"company": "cacao", "posting_date": "2026-10-31"}


CONTRASENA = "costo-importado-2026"


@pytest.fixture
def facturas_por_compania():
    """Dos compañías con una factura de compra privada en cada una."""
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
                Entity(code="cacao", name="Cacao", company_name="Cacao SA", tax_id="J-1", currency="NIO", enabled=True),
                Entity(code="cafe", name="Café", company_name="Café SA", tax_id="J-2", currency="NIO", enabled=True),
                User(
                    id="compras_cacao",
                    user="compras_cacao",
                    name="Compras Cacao",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="compras_cacao", company_code="cacao"),
            ]
        )
        database.session.flush()
        database.session.add(UOM(code="UND", name="Unidad"))
        database.session.flush()
        database.session.add(
            Item(code="ART01", name="Artículo importado", item_type="goods", is_stock_item=True, default_uom="UND")
        )
        database.session.flush()
        propia = PurchaseInvoice(
            company="cacao",
            document_type="purchase_invoice",
            document_no="FAC-CACAO-1",
            supplier_name="Proveedor Cacao",
            posting_date=date(2026, 5, 10),
            docstatus=1,
        )
        ajena = PurchaseInvoice(
            company="cafe",
            document_type="purchase_invoice",
            document_no="FAC-SECRETA-9",
            supplier_name="Proveedor Confidencial",
            posting_date=date(2026, 5, 11),
            docstatus=1,
        )
        database.session.add_all([propia, ajena])
        database.session.commit()
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        asigna_rol_a_usuario("compras_cacao", "purchasing_user")
        ids = {"propia": propia.id, "ajena": ajena.id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _login(client, usuario: str) -> None:
    """Autentica al usuario del escenario mediante el login real."""
    response = client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_alta_costo_importado_expone_factura_fuente_autorizada(facturas_por_compania):
    """El usuario con acceso a la compañía ve los metadatos de la factura fuente."""
    application, ids = facturas_por_compania
    client = application.test_client()
    _login(client, "compras_cacao")

    response = client.get(f"/buying/import-landed-cost/new?from_invoice={ids['propia']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "FAC-CACAO-1" in body
    assert "Proveedor Cacao" in body


def test_alta_costo_importado_oculta_factura_de_otra_compania(facturas_por_compania):
    """La factura de otra compañía se rechaza sin exponer sus metadatos."""
    application, ids = facturas_por_compania
    client = application.test_client()
    _login(client, "compras_cacao")

    response = client.get(f"/buying/import-landed-cost/new?from_invoice={ids['ajena']}")

    assert response.status_code == 403
    body = response.get_data(as_text=True)
    assert "FAC-SECRETA-9" not in body
    assert "Proveedor Confidencial" not in body


def test_alta_costo_importado_requiere_login(facturas_por_compania):
    """Sin sesión no se expone ninguna factura fuente."""
    application, ids = facturas_por_compania
    client = application.test_client()

    response = client.get(f"/buying/import-landed-cost/new?from_invoice={ids['ajena']}")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@pytest.mark.parametrize("datos_factura", [{}, {"from_invoice": "   "}], ids=["ausente", "blanco"])
def test_alta_costo_importado_exige_factura_fuente(facturas_por_compania, datos_factura):
    """#1760: una factura ausente o blanca no crea documento, líneas ni cargos."""
    application, _ids = facturas_por_compania
    client = application.test_client()
    _login(client, "compras_cacao")
    datos = {
        "company": "cacao",
        "posting_date": "2026-10-31",
        "allocation_method": "by_value",
        "remarks": "Alta sin factura",
        "item_item_code_0": "ART01",
        "item_item_name_0": "Artículo importado",
        "item_qty_0": "2",
        "item_uom_0": "UND",
        "item_rate_0": "10",
        "charge_concept_0": "Flete",
        "charge_type_0": "charge",
        "charge_amount_0": "15",
        **datos_factura,
    }

    response = client.post("/buying/import-landed-cost/new", data=datos)

    assert response.status_code == 200
    assert "Seleccione una factura de compra como origen para los costos de importacion." in response.get_data(as_text=True)
    with application.app_context():
        assert database.session.execute(database.select(ImportLandedCost)).scalars().all() == []
        assert database.session.execute(database.select(ImportLandedCostItem)).scalars().all() == []
        assert database.session.execute(database.select(ImportLandedCostCharge)).scalars().all() == []
