# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2131: una fila de validación por documento y filtros que no rompen la impresión."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from cacao_accounting.database import Currency, Entity, database
from cacao_accounting.printing.models import PublicDocumentValidation
from cacao_accounting.printing.service import PrintService
from cacao_accounting.printing.validation import ValidationService


@pytest.fixture
def compania_validacion(app):
    """Compañía propia para no interferir con otras filas de validación."""
    codigo = f"VAL{uuid4().hex[:5].upper()}"
    with app.app_context():
        if database.session.execute(select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.add(
            Entity(code=codigo, name="Validación", company_name="Validación SA", tax_id=codigo, currency="NIO", enabled=True)
        )
        database.session.commit()
    yield codigo
    with app.app_context():
        database.session.execute(delete(PublicDocumentValidation).where(PublicDocumentValidation.company_code == codigo))
        database.session.execute(delete(Entity).where(Entity.code == codigo))
        database.session.commit()


def _datos(company: str, **extra: object) -> dict[str, object]:
    """Carga canónica de un documento ya publicado."""
    payload: dict[str, object] = {
        "status": "posted",
        "company_code": company,
        "document_number": "F-1",
        "document_date": datetime(2026, 5, 26).date(),
    }
    payload.update(extra)
    return payload


def _filas(document_type: str, document_id: str) -> list[PublicDocumentValidation]:
    return (
        database.session.execute(
            select(PublicDocumentValidation).filter_by(document_type=document_type, document_id=document_id)
        )
        .scalars()
        .all()
    )


def test_el_esquema_rechaza_dos_filas_del_mismo_documento(app, compania_validacion):
    """El constraint único es la defensa de fondo contra la duplicación."""
    with app.app_context():
        service = ValidationService()
        service.create_or_update_validation("sales_invoice", "DOC-UQ", _datos(compania_validacion))
        database.session.commit()

        documento = PublicDocumentValidation(
            public_token=f"tok-{uuid4().hex}",
            company_code=compania_validacion,
            document_type="sales_invoice",
            document_id="DOC-UQ",
            document_number="F-1",
            document_status="posted",
            validation_hash="x" * 32,
            is_enabled=True,
        )
        database.session.add(documento)
        with pytest.raises(IntegrityError):
            database.session.flush()
        database.session.rollback()
        assert len(_filas("sales_invoice", "DOC-UQ")) == 1


def test_raza_de_publicacion_conserva_una_fila_y_su_token(app, compania_validacion, monkeypatch):
    """Si otra transacción publicó primero, la fila existente se actualiza sin duplicar."""
    with app.app_context():
        service = ValidationService()
        primera = service.create_or_update_validation("sales_invoice", "DOC-RACE", _datos(compania_validacion))
        token_original = primera.public_token
        database.session.commit()

        real = ValidationService.__dict__["_find_validation"].__func__
        lecturas = {"n": 0}

        def lectura_obsoleta(document_type: str, document_id: str):
            """Simula el snapshot previo a la publicación concurrente (#2131)."""
            lecturas["n"] += 1
            return None if lecturas["n"] == 1 else real(document_type, document_id)

        monkeypatch.setattr(ValidationService, "_find_validation", staticmethod(lectura_obsoleta))
        # La publicación ocurre dentro de la transacción del posteo, igual que en
        # producción: ahí la savepoint del intento no cierra la unidad de trabajo.
        with database.session.begin():
            segunda = service.create_or_update_validation(
                "sales_invoice", "DOC-RACE", _datos(compania_validacion, document_number="F-2")
            )

        filas = _filas("sales_invoice", "DOC-RACE")
        assert len(filas) == 1
        assert segunda is not None
        assert segunda.public_token == token_original
        assert segunda.document_number == "F-2"


@pytest.mark.parametrize(
    ("valor", "contiene"),
    [
        ("2026-05-26 10:00", "2026-05-26 10:00"),
        (datetime(2026, 5, 26, 10, 0), "2026"),
    ],
)
def test_el_filtro_datetime_no_rechaza_un_sello_de_texto(app, valor: object, contiene: str):
    """El sello de auditoría llega formateado; la plantilla del pie debe seguir imprimiendo."""
    with app.app_context():
        rendered = PrintService().env.from_string("{{ audit.printed_at | datetime }}").render(audit={"printed_at": valor})
        assert contiene in rendered
