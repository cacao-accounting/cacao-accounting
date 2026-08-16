"""Shared logistics metadata helpers for sales and purchasing documents."""

from __future__ import annotations

from datetime import date
from collections.abc import Iterable
from typing import Any

from cacao_accounting.database import Incoterm, database

INCOTERM_CODES = ("EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP", "FAS", "FOB", "CFR", "CIF")
LOGISTICS_FIELDS = ("incoterm_code", "incoterm_version", "delivery_date", "delivery_place")
TERMS_FIELDS = frozenset(("purchase_terms", "sales_terms"))


def logistics_values(source: Any = None, form: Any = None, *, terms_field: str) -> dict[str, Any]:
    """Read and normalize logistics values from a document or form."""
    if terms_field not in TERMS_FIELDS:
        raise ValueError(f"Campo de términos logísticos no permitido: {terms_field}.")
    values: dict[str, Any] = {}
    for field in (*LOGISTICS_FIELDS, terms_field):
        value = form.get(field) if form is not None else None
        if value in (None, "") and source is not None:
            value = getattr(source, field, None)
        if field == "delivery_date" and isinstance(value, str):
            try:
                value = date.fromisoformat(value) if value else None
            except ValueError as exc:
                raise ValueError("La fecha de entrega no es válida.") from exc
        values[field] = value or None
    if values["incoterm_code"] and not values["incoterm_version"]:
        values["incoterm_version"] = "2020"
    return values


def validate_incoterm(values: dict[str, Any], allowed_codes: Iterable[str] | None = None) -> None:
    """Reject inactive or unknown Incoterms supplied by forms or APIs.

    ``allowed_codes`` permits callers and tests to inject a catalog without
    requiring an active database session.
    """
    code = values.get("incoterm_code")
    if not code:
        return
    version = values.get("incoterm_version") or "2020"
    if allowed_codes is None:
        active = database.session.execute(database.select(Incoterm.code).where(Incoterm.is_active.is_(True))).all()
        allowed = {row[0] for row in active} if active else set(INCOTERM_CODES)
    else:
        allowed = set(allowed_codes)
    if code not in allowed or version != "2020":
        raise ValueError(f"El Incoterm {code} ({version}) no está disponible.")


def copy_logistics(
    target: Any,
    source: Any = None,
    form: Any = None,
    *,
    terms_field: str,
    allowed_incoterms: Iterable[str] | None = None,
) -> None:
    """Validate and copy logistics metadata to a target document."""
    values = logistics_values(source, form, terms_field=terms_field)
    validate_incoterm(values, allowed_incoterms)
    for field, value in values.items():
        setattr(target, field, value)


def logistics_signature(document: Any, *, terms_field: str) -> tuple[Any, ...]:
    """Return the immutable logistics identity used for compatibility checks."""
    values = logistics_values(document, terms_field=terms_field)
    return tuple(values[field] for field in (*LOGISTICS_FIELDS, terms_field))


def ensure_compatible_logistics(documents: Iterable[Any], *, terms_field: str) -> None:
    """Reject a target document assembled from incompatible logistics terms."""
    signatures = {logistics_signature(document, terms_field=terms_field) for document in documents}
    if len(signatures) > 1:
        raise ValueError("Las cotizaciones seleccionadas tienen condiciones logísticas incompatibles.")


def incoterm_options() -> list[dict[str, str]]:
    """Return active Incoterms for form controls, with a safe dev fallback."""
    rows = (
        database.session.execute(database.select(Incoterm).where(Incoterm.is_active.is_(True)).order_by(Incoterm.code))
        .scalars()
        .all()
    )
    if rows:
        return [{"code": row.code, "label": row.name, "version": row.version} for row in rows]
    return [{"code": code, "label": code, "version": "2020"} for code in INCOTERM_CODES]
