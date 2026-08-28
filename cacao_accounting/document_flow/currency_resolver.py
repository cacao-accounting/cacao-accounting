# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Primitivas comunes para resolucion y validacion de moneda transaccional.

Refs: #758

El contrato de moneda exige que toda transaccion persistida tenga una
moneda transaccional explicita y que el posting rechace cualquier inferencia
silenciosa. Este modulo concentra la prelacion:

    1. Moneda seleccionada explicitamente por el usuario.
    2. Moneda del documento origen en Document Flow (heredada, no sustituible).
    3. Moneda predeterminada del tercero.
    4. Moneda funcional de la compania.

Cuando existe un origen de Document Flow la moneda se hereda obligatoriamente;
el usuario no puede sustituirla y los origenes deben compartir moneda o la
operacion se rechaza antes de crear el documento derivado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from cacao_accounting.database import Entity, database
from cacao_accounting.document_flow import DocumentFlowError


@dataclass(frozen=True)
class ResolvedCurrency:
    """Resultado de la resolucion de moneda transaccional."""

    transaction_currency: str
    base_currency: str
    source: str  # user | source | party | company


def company_functional_currency(company: str | None) -> str | None:
    """Devuelve la moneda funcional vigente de la compania o ``None``.

    No aplica fallback; devuelve ``None`` cuando la compania no existe o no
    tiene moneda funcional configurada. Los consumidores deben tratar el
    resultado como dato y nunca como inferencia.
    """
    if not company:
        return None
    entity = database.session.execute(database.select(Entity).filter_by(code=company)).scalars().first()
    if entity is None:
        return None
    return str(entity.currency) if entity.currency else None


def _require_explicit_currency(code: str | None, *, context: str) -> str:
    """Falla si la moneda es vacia o no es una cadena valida."""
    if not code or not isinstance(code, str) or not code.strip():
        raise DocumentFlowError(
            f"La {context} requiere una moneda transaccional explicita antes de persistirse.",
            400,
        )
    return code.strip()


def source_transaction_currencies(sources: Sequence[Any] | None) -> list[str]:
    """Devuelve la lista de monedas transaccionales explicitas de cada origen.

    Un origen sin ``transaction_currency`` falla explicitamente; nunca se
    infiere desde la compania para preservar la regla de no-inferencia.
    """
    if not sources:
        return []
    currencies: list[str] = []
    for source in sources:
        currency = getattr(source, "transaction_currency", None)
        if not currency:
            raise DocumentFlowError(
                "El documento origen no tiene moneda transaccional explicita; " "no se permite inferirla desde la compania.",
                400,
            )
        currencies.append(str(currency))
    return currencies


def validate_flow_currency_homogeneity(sources: Sequence[Any] | None) -> str | None:
    """Valida que todos los origenes compartan la misma moneda transaccional.

    Devuelve la moneda comun cuando existe o ``None`` cuando no hay origenes.
    Lanza ``DocumentFlowError`` cuando los origenes existen pero mezclan
    monedas o cuando alguno carece de ``transaction_currency`` explicita.
    """
    if not sources:
        return None
    currencies = source_transaction_currencies(sources)
    first = currencies[0]
    for index, currency in enumerate(currencies[1:], start=1):
        if currency != first:
            raise DocumentFlowError(
                "Los documentos origen usan monedas distintas "
                f"({first!r} vs {currency!r} en el origen #{index + 1}); "
                "no se permite crear el documento derivado.",
                400,
            )
    return first


def resolve_party_currency(party: Any | None) -> str | None:
    """Devuelve la moneda predeterminada de un tercero sin aplicar fallback."""
    if party is None:
        return None
    currency = getattr(party, "default_currency", None) or getattr(party, "currency", None)
    return str(currency) if currency else None


def resolve_transaction_currency(
    *,
    company: str | None,
    party: Any | None = None,
    user_selection: str | None = None,
    sources: Sequence[Any] | None = None,
    context: str = "documento",
) -> ResolvedCurrency:
    """Resuelve la moneda transaccional segun la prelacion del contrato.

    Reglas:

    - Si hay origenes de Document Flow se exige moneda homogenea explicita;
      el usuario no puede sustituirla.
    - Si no hay origenes y el usuario eligio moneda, gana la eleccion.
    - Si no hay eleccion del usuario, se usa la moneda del tercero.
    - Como ultimo recurso se usa la moneda funcional de la compania.

    El resultado siempre incluye ``transaction_currency`` y ``base_currency``
    explicitas; la funcion nunca devuelve valores nulos en presencia de
    compania configurada.
    """
    base_currency = company_functional_currency(company)
    if not base_currency:
        raise DocumentFlowError(
            f"La compania {company!r} requiere una moneda funcional configurada antes de crear {context}.",
            400,
        )

    if sources:
        inherited = validate_flow_currency_homogeneity(sources)
        if inherited and user_selection and user_selection != inherited:
            raise DocumentFlowError(
                f"La moneda del {context} no puede diferir de la heredada por Document Flow "
                f"({inherited!r} vs {user_selection!r}).",
                400,
            )
        return ResolvedCurrency(
            transaction_currency=_require_explicit_currency(inherited, context=context),
            base_currency=base_currency,
            source="source",
        )

    if user_selection:
        return ResolvedCurrency(
            transaction_currency=_require_explicit_currency(user_selection, context=context),
            base_currency=base_currency,
            source="user",
        )

    party_currency = resolve_party_currency(party)
    if party_currency:
        return ResolvedCurrency(
            transaction_currency=_require_explicit_currency(party_currency, context=context),
            base_currency=base_currency,
            source="party",
        )

    return ResolvedCurrency(
        transaction_currency=_require_explicit_currency(base_currency, context=context),
        base_currency=base_currency,
        source="company",
    )


def assert_currency_explicit(
    document: Any | None,
    *,
    field: str = "transaction_currency",
    context: str = "documento",
) -> str:
    """Asegura que un documento persistido tenga la moneda transaccional.

    A diferencia de ``resolve_transaction_currency`` esta funcion no infiere;
    un documento guardado sin moneda se considera invalido y se rechaza con
    ``DocumentFlowError``. Pensada para validacion al transicionar de borrador
    a aprobado.
    """
    if document is None:
        raise DocumentFlowError(f"{context.capitalize()} no encontrado.", 404)
    value = getattr(document, field, None)
    if not value or not isinstance(value, str) or not value.strip():
        raise DocumentFlowError(
            f"El {context} requiere una {field} explicita antes de contabilizarse.",
            400,
        )
    return value.strip()


def assert_base_currency_snapshot(
    document: Any | None,
    *,
    company: str | None,
    context: str = "documento",
) -> str:
    """Asegura que el documento tenga snapshot de ``base_currency`` consistente.

    El snapshot se persiste al crear el borrador y debe coincidir con la moneda
    funcional vigente de la compania. Si difiere, el documento requiere
    revalidacion; en caso de no existir, se rechaza.
    """
    if document is None:
        raise DocumentFlowError(f"{context.capitalize()} no encontrado.", 404)
    expected = company_functional_currency(company)
    if not expected:
        raise DocumentFlowError(
            f"La compania {company!r} requiere una moneda funcional configurada.",
            400,
        )
    snapshot = getattr(document, "base_currency", None)
    if not snapshot or not isinstance(snapshot, str) or not snapshot.strip():
        raise DocumentFlowError(
            f"El {context} requiere un snapshot de base_currency explicito antes de contabilizarse.",
            400,
        )
    if snapshot != expected:
        raise DocumentFlowError(
            f"El snapshot de base_currency del {context} ({snapshot!r}) no coincide con la "
            f"moneda funcional vigente ({expected!r}); el documento requiere revalidacion.",
            400,
        )
    return expected


def collect_sources_from_relations(
    document: Any,
    relation_attr: str = "source_relations",
) -> list[Any]:
    """Recupera los documentos origen desde una coleccion de relaciones.

    Helper que evita repetir la logica de extraccion de fuentes en cada
    consumidor. Devuelve una lista de instancias ``Any`` con
    ``transaction_currency`` accesible.
    """
    relations = getattr(document, relation_attr, None)
    if not relations:
        return []
    sources: list[Any] = []
    for relation in relations:
        source = getattr(relation, "source", None)
        if source is not None:
            sources.append(source)
    return sources


__all__ = [
    "ResolvedCurrency",
    "assert_base_currency_snapshot",
    "assert_currency_explicit",
    "collect_sources_from_relations",
    "company_functional_currency",
    "resolve_party_currency",
    "resolve_transaction_currency",
    "source_transaction_currencies",
    "validate_flow_currency_homogeneity",
]
