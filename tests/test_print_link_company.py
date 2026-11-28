# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2055: la impresión usa la compañía del documento y no la compañía activa."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.auth.permisos import cargar_permisos_predeterminados
from cacao_accounting.auth.roles import crea_roles_predeterminados
from cacao_accounting.database import SalesRequest, UserCompanyAccess, database


def _pdf_disponible() -> bool:
    """Indica si WeasyPrint puede generar PDFs en este entorno."""
    try:
        from weasyprint import HTML

        HTML(string="<p>prueba</p>").write_pdf()
    except Exception:
        return False
    return True


@pytest.fixture
def documento_alpha(app, reference_users):
    """Pedido de venta en alpha con acceso temporal del administrador."""
    admin_id = str(reference_users["admin"].id)
    with app.app_context():
        crea_roles_predeterminados()
        cargar_permisos_predeterminados()
        acceso = database.session.execute(
            select(UserCompanyAccess).filter_by(user_id=admin_id, company_code="alpha")
        ).scalar_one_or_none()
        creado = acceso is None
        if creado:
            database.session.add(UserCompanyAccess(user_id=admin_id, company_code="alpha"))
        documento = SalesRequest(
            company="alpha",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SR-2055-{uuid4().hex[:6]}",
            customer_name="Cliente Alpha",
        )
        database.session.add(documento)
        database.session.commit()
        documento_id, numero = str(documento.id), str(documento.document_no)

    yield documento_id, numero

    with app.app_context():
        if creado:
            database.session.execute(
                database.delete(UserCompanyAccess).where(
                    UserCompanyAccess.user_id == admin_id, UserCompanyAccess.company_code == "alpha"
                )
            )
            database.session.commit()


def test_detalle_y_preview_usan_la_compania_del_documento(documento_alpha, authenticated_client):
    """Con compañía activa distinta, el enlace y la vista previa usan alpha."""
    documento_id, numero = documento_alpha
    client = authenticated_client("admin")

    detalle = client.get(f"/sales/sales-request/{documento_id}")
    preview = client.get(f"/print/sales_request/{documento_id}/preview?company=alpha")

    assert detalle.status_code == 200
    assert "company=alpha" in detalle.get_data(as_text=True)
    assert preview.status_code == 200
    assert numero in preview.get_data(as_text=True)


@pytest.mark.skipif(not _pdf_disponible(), reason="WeasyPrint sin librerías nativas; CI Linux cubre el PDF")
def test_pdf_usa_la_compania_del_documento(documento_alpha, authenticated_client):
    """El PDF del documento de otra compañía se genera con su compañía."""
    documento_id, _ = documento_alpha
    client = authenticated_client("admin")

    pdf = client.get(f"/print/sales_request/{documento_id}/pdf?company=alpha")

    assert pdf.status_code == 200
    assert pdf.data.startswith(b"%PDF")
