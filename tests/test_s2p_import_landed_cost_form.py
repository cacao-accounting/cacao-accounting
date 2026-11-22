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
    Modules,
    PurchaseInvoice,
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


def test_import_landed_cost_form_renders_company_and_date_once(client, reference_users):
    """The shared header owns company/date fields without duplicate controls."""
    with client.session_transaction() as session:
        session["_user_id"] = str(reference_users["admin"].id)
        session["_fresh"] = True

    response = client.get("/buying/import-landed-cost/new?company=alpha&posting_date=2026-10-31")

    assert response.status_code == 200
    parser = _FormFieldParser()
    parser.feed(response.get_data(as_text=True))

    for field in ("company", "posting_date"):
        assert parser.ids[field] == 1
        assert parser.names[field] == 1

    assert parser.transaction_config is not None
    assert parser.transaction_config["initialHeader"] == {"company": "alpha", "posting_date": "2026-10-31"}


def test_import_landed_cost_form_preserves_fields_after_invalid_post(client, reference_users):
    """An invalid allocation method returns the submitted company and date to the form."""
    with client.session_transaction() as session:
        session["_user_id"] = str(reference_users["admin"].id)
        session["_fresh"] = True

    response = client.post(
        "/buying/import-landed-cost/new",
        data={"company": "alpha", "posting_date": "2026-10-31", "allocation_method": "invalid"},
    )

    assert response.status_code == 200
    parser = _FormFieldParser()
    parser.feed(response.get_data(as_text=True))
    assert parser.transaction_config is not None
    assert parser.transaction_config["initialHeader"] == {"company": "alpha", "posting_date": "2026-10-31"}


def test_import_landed_cost_invalid_post_prefers_submitted_values_over_query(client, reference_users):
    """An invalid POST re-renders the submitted values, not stale URL filters."""
    with client.session_transaction() as session:
        session["_user_id"] = str(reference_users["admin"].id)
        session["_fresh"] = True

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
