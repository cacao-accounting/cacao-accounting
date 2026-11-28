# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William Moreno Reyes

"""#2287: importación CSV hasta publicación GL multilibro con monedas distintas."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.contabilidad.journal_service import JournalValidationError, submit_journal
from cacao_accounting.contabilidad.posting_service import PostingError
from cacao_accounting.database import (
    Book,
    ComprobanteContable,
    ExchangeRate,
    GLEntry,
    User,
    database,
)
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services.import_service import ImportService


def _crear_lote(app, tmp_path, encabezados, filas, *, accounting_book_id=""):
    ruta = tmp_path / f"comprobante-{uuid4().hex[:8]}.csv"
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(encabezados)
        escritor.writerows(filas)

    with app.app_context():
        actor = database.session.execute(select(User.id).filter_by(user="admin")).scalar_one()
        lote = ImportBatch(
            company_id="cacao",
            record_type="journal_entry",
            source_format="csv",
            source_filename=ruta.name,
            source_path=str(ruta),
            import_status=1,
            accounting_book_id=accounting_book_id or None,
            created_by=actor,
        )
        database.session.add(lote)
        database.session.commit()
        return lote.id


def _setup_two_books_usd(app):
    with app.app_context():
        niif = database.session.execute(select(Book).filter_by(code="NIIF")).scalar_one()
        niif.currency = "USD"
        for origin, destination, rate in [
            ("USD", "NIO", Decimal("36.50")),
            ("NIO", "USD", Decimal("1") / Decimal("36.50")),
        ]:
            exists = database.session.execute(
                select(ExchangeRate).filter_by(origin=origin, destination=destination)
            ).scalar_one_or_none()
            if exists:
                exists.rate = rate
                exists.date = date(2026, 5, 1)
            else:
                database.session.add(ExchangeRate(origin=origin, destination=destination, rate=rate, date=date(2026, 5, 1)))
        database.session.commit()


def _import_and_get_journal(app, lote_id):
    with app.app_context():
        svc = ImportService()
        assert svc.validate(lote_id)
        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 3, [e.message for e in ImportBatchError.query.filter_by(batch_id=lote_id).all()]
        assert svc.execute(lote_id)
        database.session.remove()
        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 5
        journal = (
            database.session.execute(
                select(ComprobanteContable)
                .where(ComprobanteContable.entity == "cacao")
                .order_by(ComprobanteContable.created.desc())
            )
            .scalars()
            .first()
        )
        assert journal is not None
        return journal.id


def test_import_multilibro_dos_monedas_publica_gl_por_libro(entorno_contable_aislado, tmp_path):
    app = entorno_contable_aislado.app
    _setup_two_books_usd(app)
    encabezados = ["document_ref", "fecha", "cuenta", "debito", "credito", "moneda", "tipo_cambio", "descripcion"]
    filas = [
        ["AS-2287", "2026-05-15", "1101", "100", "0", "USD", "36.50", "Caja USD"],
        ["AS-2287", "2026-05-15", "4101", "0", "3650", "NIO", "1", "Ingreso NIO"],
    ]
    lote_id = _crear_lote(app, tmp_path, encabezados, filas)
    journal_id = _import_and_get_journal(app, lote_id)

    with app.app_context():
        actor = database.session.execute(select(User.id).filter_by(user="admin")).scalar_one()
        submit_journal(journal_id, user_id=actor)
        database.session.commit()

        default_book = database.session.execute(select(Book).filter_by(code="DEFAULT_BOOK")).scalar_one()
        niif_book = database.session.execute(select(Book).filter_by(code="NIIF")).scalar_one()
        entries = (
            database.session.execute(
                select(GLEntry).where(
                    GLEntry.voucher_type == "journal_entry", GLEntry.voucher_id == journal_id, GLEntry.is_cancelled.is_(False)
                )
            )
            .scalars()
            .all()
        )
        by_book = {}
        for e in entries:
            by_book.setdefault(e.ledger_id, []).append(e)
        assert set(by_book) == {default_book.id, niif_book.id}
        # DEFAULT_BOOK NIO: 100 USD * 36.5 = 3650 NIO debit, 3650 NIO credit
        nio = sorted(by_book[default_book.id], key=lambda x: (x.debit, x.credit))
        assert [(e.debit, e.credit) for e in nio] == [
            (Decimal("0"), Decimal("3650.0000")),
            (Decimal("3650.0000"), Decimal("0")),
        ]
        # NIIF USD: 100 USD debit, 3650 NIO / 36.5 = 100 USD credit
        usd = sorted(by_book[niif_book.id], key=lambda x: (x.debit, x.credit))
        assert [(e.debit, e.credit) for e in usd] == [(Decimal("0"), Decimal("100.0000")), (Decimal("100.0000"), Decimal("0"))]


def test_import_multilibro_tasa_ausente_sin_historica_rechaza_atomico(entorno_contable_aislado, tmp_path):
    """El rechazo por FX ausente es discriminante y no deja documento ni GL.

    El lote puede rechazarse en validación o al ejecutar la importación; en
    ambas fases se exige un error de tasa/cambio y ausencia de evidencia parcial.
    """
    app = entorno_contable_aislado.app
    _setup_two_books_usd(app)
    with app.app_context():
        database.session.execute(
            database.delete(ExchangeRate).where(
                ((ExchangeRate.origin == "USD") & (ExchangeRate.destination == "NIO"))
                | ((ExchangeRate.origin == "NIO") & (ExchangeRate.destination == "USD"))
            )
        )
        database.session.commit()
    encabezados = ["document_ref", "fecha", "cuenta", "debito", "credito", "moneda", "tipo_cambio", "descripcion"]
    filas = [
        ["AS-2287-NR", "2026-05-15", "1101", "100", "0", "USD", "", "Caja USD"],
        ["AS-2287-NR", "2026-05-15", "4101", "0", "100", "USD", "", "Ingreso USD"],
    ]
    lote_id = _crear_lote(app, tmp_path, encabezados, filas)
    with app.app_context():
        svc = ImportService()
        assert svc.validate(lote_id)
        lote = database.session.get(ImportBatch, lote_id)
        # Draft validation may pass with rate 1 fallback; posting must reject atomically.
        if lote.import_status == 3:
            assert svc.execute(lote_id)
            database.session.remove()
            lote = database.session.get(ImportBatch, lote_id)
            if lote.import_status == 5:
                journal = (
                    database.session.execute(
                        select(ComprobanteContable)
                        .where(ComprobanteContable.entity == "cacao")
                        .order_by(ComprobanteContable.created.desc())
                    )
                    .scalars()
                    .first()
                )
                assert journal is not None
                actor = database.session.execute(select(User.id).filter_by(user="admin")).scalar_one()
                with pytest.raises((JournalValidationError, PostingError)) as exc_info:
                    submit_journal(journal.id, user_id=actor)
                msg = str(exc_info.value).lower()
                assert "cambio" in msg or "exchange" in msg
                database.session.rollback()
                assert (
                    database.session.execute(select(GLEntry.id).where(GLEntry.voucher_id == journal.id)).scalar_one_or_none()
                    is None
                )
                return
        # Rechazo antes de publicar: el error debe identificar la causa FX.
        errors = ImportBatchError.query.filter_by(batch_id=lote_id).all()
        assert errors, "Lote rechazado debe registrar error de tasa ausente"
        detalle = " | ".join(f"{error.error_type}: {error.message}" for error in errors).lower()
        assert "cambio" in detalle or "exchange" in detalle or "tasa" in detalle, detalle
        assert (
            database.session.execute(select(ComprobanteContable.id).where(ComprobanteContable.entity == "cacao"))
            .scalars()
            .first()
            is None
        ), "El rechazo por FX no debe dejar un comprobante en borrador"
        assert database.session.execute(select(GLEntry.id)).scalar_one_or_none() is None


def test_import_multilibro_tasa_historica_sin_explicita_publica(entorno_contable_aislado, tmp_path):
    """Sin tipo_cambio explícito, posting usa tasa histórica por libro y publica."""
    app = entorno_contable_aislado.app
    _setup_two_books_usd(app)
    encabezados = ["document_ref", "fecha", "cuenta", "debito", "credito", "moneda", "tipo_cambio", "descripcion"]
    filas = [
        ["AS-2287-H", "2026-05-15", "1101", "100", "0", "USD", "", "Caja USD"],
        ["AS-2287-H", "2026-05-15", "4101", "0", "100", "USD", "", "Ingreso USD"],
    ]
    lote_id = _crear_lote(app, tmp_path, encabezados, filas)
    journal_id = _import_and_get_journal(app, lote_id)

    with app.app_context():
        actor = database.session.execute(select(User.id).filter_by(user="admin")).scalar_one()
        submit_journal(journal_id, user_id=actor)
        database.session.commit()

        default_book = database.session.execute(select(Book).filter_by(code="DEFAULT_BOOK")).scalar_one()
        niif_book = database.session.execute(select(Book).filter_by(code="NIIF")).scalar_one()
        entries = (
            database.session.execute(
                select(GLEntry).where(
                    GLEntry.voucher_type == "journal_entry",
                    GLEntry.voucher_id == journal_id,
                    GLEntry.is_cancelled.is_(False),
                )
            )
            .scalars()
            .all()
        )
        by_book = {}
        for e in entries:
            by_book.setdefault(e.ledger_id, []).append(e)
        assert set(by_book) == {default_book.id, niif_book.id}
        nio = sorted(by_book[default_book.id], key=lambda x: (x.debit, x.credit))
        assert [(e.debit, e.credit) for e in nio] == [
            (Decimal("0"), Decimal("3650.0000")),
            (Decimal("3650.0000"), Decimal("0")),
        ]
        usd = sorted(by_book[niif_book.id], key=lambda x: (x.debit, x.credit))
        assert [(e.debit, e.credit) for e in usd] == [
            (Decimal("0"), Decimal("100.0000")),
            (Decimal("100.0000"), Decimal("0")),
        ]


def test_import_multilibro_tasa_invalida_y_descuadre_rechaza(entorno_contable_aislado, tmp_path):
    app = entorno_contable_aislado.app
    _setup_two_books_usd(app)
    encabezados = ["document_ref", "fecha", "cuenta", "debito", "credito", "moneda", "tipo_cambio", "descripcion"]
    lote_bad_rate = _crear_lote(
        app,
        tmp_path,
        encabezados,
        [
            ["AS-2287-BR", "2026-05-15", "1101", "100", "0", "USD", "abc", "Caja"],
            ["AS-2287-BR", "2026-05-15", "4101", "0", "3650", "NIO", "1", "Ingreso"],
        ],
    )
    lote_unbalanced = _crear_lote(
        app,
        tmp_path,
        encabezados,
        [
            ["AS-2287-UB", "2026-05-15", "1101", "100", "0", "USD", "36.50", "Caja"],
            ["AS-2287-UB", "2026-05-15", "4101", "0", "3000", "NIO", "1", "Ingreso"],
        ],
    )
    with app.app_context():
        svc = ImportService()
        assert svc.validate(lote_bad_rate)
        bad_errors = ImportBatchError.query.filter_by(batch_id=lote_bad_rate).all()
        assert any(e.error_type == "BUSINESS_RULE" for e in bad_errors)
        assert svc.validate(lote_unbalanced)
        unbalanced_errors = ImportBatchError.query.filter_by(batch_id=lote_unbalanced).all()
        assert any("no esta balanceado" in e.message.lower() for e in unbalanced_errors)
        assert database.session.execute(select(GLEntry.id)).scalar_one_or_none() is None
        assert (
            database.session.execute(select(ComprobanteContable.id).where(ComprobanteContable.entity == "cacao"))
            .scalars()
            .first()
            is None
        )
