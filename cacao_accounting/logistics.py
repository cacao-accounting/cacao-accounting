"""Shared logistics metadata helpers for sales and purchasing documents."""

from __future__ import annotations

from datetime import date
from typing import Any

from cacao_accounting.database import Incoterm, database

INCOTERM_CODES = ("EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP", "FAS", "FOB", "CFR", "CIF")
LOGISTICS_FIELDS = ("incoterm_code", "incoterm_version", "delivery_date", "delivery_place")


def logistics_values(source: Any = None, form: Any = None, *, terms_field: str) -> dict[str, Any]:
    """Read and normalize logistics values from a document or form."""
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


def validate_incoterm(values: dict[str, Any]) -> None:
    """Reject inactive or unknown Incoterms supplied by forms or APIs."""
    code = values.get("incoterm_code")
    if not code:
        return
    version = values.get("incoterm_version") or "2020"
    active = database.session.execute(database.select(Incoterm.code).where(Incoterm.is_active.is_(True))).all()
    allowed = {row[0] for row in active} if active else set(INCOTERM_CODES)
    if code not in allowed or version != "2020":
        raise ValueError(f"El Incoterm {code} ({version}) no está disponible.")


def copy_logistics(target: Any, source: Any = None, form: Any = None, *, terms_field: str) -> None:
    """Validate and copy logistics metadata to a target document."""
    values = logistics_values(source, form, terms_field=terms_field)
    validate_incoterm(values)
    for field, value in values.items():
        setattr(target, field, value)


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
