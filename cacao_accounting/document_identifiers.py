# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios para resolver series e identificadores documentales."""

from __future__ import annotations

import json
from datetime import date
from typing import cast

from cacao_accounting.database import (
    AccountingPeriod,
    ExternalCounter,
    ExternalCounterAuditLog,
    ExternalNumberUsage,
    FiscalYear,
    NamingSeries,
    Sequence,
    SeriesExternalCounterMap,
    SeriesSequenceMap,
    database,
)
from cacao_accounting.database.helpers import generate_identifier, get_active_naming_series


class IdentifierConfigurationError(ValueError):
    """Error controlado para configuraciones de series e identificadores."""


class ExternalNumberDuplicateError(IdentifierConfigurationError):
    """Error al intentar usar un numero externo ya registrado en el mismo contador."""


EL_CONTADOR_EXTERNO_NO_EXISTE = "El contador externo no existe."
EL_CONTADOR_EXTERNO_ESTA_INACTIVO = "El contador externo esta inactivo."

# -------------------------------------------------------------------------------------
# Parsing y validaciones de datos de entrada
# -------------------------------------------------------------------------------------


def parse_posting_date(posting_date_raw: date | str | None) -> date:
    """Normaliza la fecha contable para usarla en series y validaciones."""
    if isinstance(posting_date_raw, date):
        return posting_date_raw
    if not posting_date_raw:
        raise IdentifierConfigurationError("Debe indicar la fecha de contabilizacion.")

    try:
        return date.fromisoformat(str(posting_date_raw))
    except ValueError as exc:
        raise IdentifierConfigurationError("La fecha de contabilizacion es invalida.") from exc


def validate_accounting_period(company: str | None, posting_date: date, allow_closing: bool = False) -> None:
    """Valida que la fecha contable no caiga en un periodo cerrado.

    Solo se permite un comprobante manual de cierre (`is_closing=True`) si el periodo
    contable está cerrado. Si el año fiscal está cerrado, no se permite ningún movimiento.
    """
    if not company:
        raise IdentifierConfigurationError("Debe indicar la compania del documento.")

    closed_fiscal_year = database.session.execute(
        database.select(FiscalYear)
        .filter_by(entity=company, is_closed=True)
        .where(FiscalYear.year_start_date <= posting_date)
        .where(FiscalYear.year_end_date >= posting_date)
    ).scalar_one_or_none()

    if closed_fiscal_year and not allow_closing:
        raise IdentifierConfigurationError("No puede registrar documentos en un año fiscal cerrado.")

    closed_period = database.session.execute(
        database.select(AccountingPeriod)
        .filter_by(entity=company, is_closed=True)
        .where(AccountingPeriod.start <= posting_date)
        .where(AccountingPeriod.end >= posting_date)
    ).scalar_one_or_none()

    if closed_period and not allow_closing:
        raise IdentifierConfigurationError("No puede registrar documentos en un periodo contable cerrado.")


def enforce_single_default_series(entity_type: str, company: str | None, exclude_id: str | None = None) -> None:
    """Garantiza que solo exista una serie predeterminada activa por entity_type + company.

    Desmarca como predeterminadas las demas series para la misma combinacion
    entity_type + company antes de marcar la nueva como predeterminada.

    Args:
        entity_type: Tipo de entidad (ej: 'sales_invoice')
        company: Codigo de compania o None para series globales
        exclude_id: ID de la serie que se quiere mantener como predeterminada (se excluye del reset)
    """
    query = database.select(NamingSeries).filter(
        NamingSeries.entity_type == entity_type,
        NamingSeries.is_default.is_(True),
    )

    if company:
        query = query.filter(NamingSeries.company == company)
    else:
        query = query.filter(NamingSeries.company.is_(None))

    existing_defaults = database.session.execute(query).scalars().all()
    for series in existing_defaults:
        if series.id != exclude_id:
            series.is_default = False

    database.session.flush()


# -------------------------------------------------------------------------------------
# Seleccion de series internas
# -------------------------------------------------------------------------------------


def _pick_naming_series(entity_type: str, company: str, naming_series_id: str | None) -> NamingSeries:
    """Selecciona la serie activa por doctype y compania.

    Orden de preferencia:
    1. Serie explicitamente solicitada (naming_series_id)
    2. Serie marcada como predeterminada para la compania
    3. Primera serie activa de la compania (orden alfabetico)
    4. Primera serie global activa
    5. Serie creada automaticamente por bootstrap
    """
    if naming_series_id:
        selected = database.session.get(NamingSeries, naming_series_id)
        if not selected or not selected.is_active:
            raise IdentifierConfigurationError("La serie seleccionada no existe o esta inactiva.")
        if selected.entity_type != entity_type:
            raise IdentifierConfigurationError("La serie seleccionada no coincide con el tipo de documento.")
        if selected.company not in (None, company):
            raise IdentifierConfigurationError("La serie seleccionada no pertenece a la compania indicada.")
        return selected

    candidates = get_active_naming_series(entity_type=entity_type, company=company)
    if not candidates:
        return _create_default_series(entity_type=entity_type, company=company)

    exact_company_matches = [series for series in candidates if series.company == company]
    company_defaults = [series for series in exact_company_matches if series.is_default]
    if company_defaults:
        return sorted(company_defaults, key=lambda row: row.name)[0]

    if exact_company_matches:
        return sorted(exact_company_matches, key=lambda row: row.name)[0]

    global_matches = [series for series in candidates if series.company is None]
    global_defaults = [series for series in global_matches if series.is_default]
    if global_defaults:
        return sorted(global_defaults, key=lambda row: row.name)[0]

    return sorted(global_matches, key=lambda row: row.name)[0]


def ensure_default_naming_series_for_company(company: str, entity_types: list[str] | None = None) -> None:
    """Crea las series predeterminadas para una compañia cuando no existen."""
    if entity_types is None:
        entity_types = [
            "journal_entry",
            "sales_invoice",
            "purchase_invoice",
            "payment_entry",
            "stock_entry",
            "purchase_order",
            "purchase_receipt",
            "purchase_request",
            "purchase_quotation",
            "supplier_quotation",
            "sales_order",
            "sales_request",
            "sales_quotation",
            "delivery_note",
        ]
    for entity_type in entity_types:
        _pick_naming_series(entity_type=entity_type, company=company, naming_series_id=None)


def _default_entity_code(entity_type: str) -> str:
    """Devuelve abreviacion de doctype para prefijos de series."""
    map_codes = {
        "purchase_request": "PREQ",
        "purchase_quotation": "RFQ",
        "supplier_quotation": "SPQ",
        "purchase_order": "PO",
        "purchase_receipt": "PR",
        "purchase_invoice": "PI",
        "sales_order": "SO",
        "sales_request": "SR",
        "delivery_note": "DN",
        "sales_invoice": "SI",
        "sales_quotation": "SQ",
        "payment_entry": "PAY",
        "stock_entry": "STE",
    }
    return map_codes.get(entity_type, entity_type[:3].upper())


def _create_default_series(entity_type: str, company: str) -> NamingSeries:
    """Crea una serie y secuencia por defecto para compania + doctype.

    La serie creada automaticamente se marca como predeterminada (is_default=True)
    ya que es la primera y unica para esta combinacion.
    """
    code = _default_entity_code(entity_type)
    sequence = Sequence(
        name=f"{company} {entity_type} sequence",
        current_value=0,
        increment=1,
        padding=5,
        reset_policy="yearly",
    )
    database.session.add(sequence)
    database.session.flush()

    naming_series = NamingSeries(
        name=f"{company}-{code}",
        entity_type=entity_type,
        company=company,
        prefix_template=f"*COMP*-{code}-*YYYY*-*MM*-",
        is_active=True,
        is_default=True,
    )
    database.session.add(naming_series)
    database.session.flush()

    database.session.add(
        SeriesSequenceMap(
            naming_series_id=naming_series.id,
            sequence_id=sequence.id,
            priority=0,
            condition=None,
        )
    )
    database.session.flush()
    return naming_series


def _pick_sequence_id(naming_series_id: str) -> str:
    """Selecciona la secuencia con mayor prioridad para la serie."""
    mapping = (
        database.session.execute(
            database.select(SeriesSequenceMap)
            .filter_by(naming_series_id=naming_series_id)
            .order_by(SeriesSequenceMap.priority.asc())
        )
        .scalars()
        .first()
    )

    if not mapping:
        raise IdentifierConfigurationError("La serie seleccionada no tiene una secuencia asociada.")

    return mapping.sequence_id


# -------------------------------------------------------------------------------------
# Seleccion de contadores externos (GAP 4 & GAP 5)
# -------------------------------------------------------------------------------------


def _condition_matches(condition_json: str | None, context: dict) -> bool:
    """Evalua si condition_json es compatible con el contexto dado.

    Una condicion nula/vacia siempre coincide (es el contador predeterminado).
    Una condicion no nula solo coincide si TODOS sus pares clave:valor
    estan presentes en el contexto con el mismo valor.

    Args:
        condition_json: JSON serializado de condiciones (puede ser None)
        context: Diccionario de contexto del documento (payment_method, bank_account_id, etc.)

    Returns:
        True si la condicion aplica para el contexto dado.
    """
    if not condition_json:
        return True
    try:
        conditions = json.loads(condition_json)
    except (json.JSONDecodeError, ValueError):
        return False
    if not isinstance(conditions, dict):
        return False
    return all(context.get(k) == v for k, v in conditions.items())


def _resolve_external_counter(
    naming_series_id: str,
    context: dict | None = None,
    explicit_counter_id: str | None = None,
) -> ExternalCounter | None:
    """Resuelve el contador externo mas apropiado para una serie dada.

    Orden de resolucion:
    1. Si explicit_counter_id se provee, usarlo directamente (validando que exista y este activo).
    2. Buscar en SeriesExternalCounterMap para la serie:
       a. Filtrar candidatos con condicion que coincida con el contexto.
       b. Priorizar por numero de condiciones coincidentes (mas especifico primero).
       c. Fallback: entry sin condicion (condition_json IS NULL).
    3. Si no hay mapeo, retornar None (sin contador externo).

    Args:
        naming_series_id: ID de la NamingSeries activa
        context: Contexto del documento (payment_method, bank_account_id, etc.)
        explicit_counter_id: ID de ExternalCounter explicitamente seleccionado

    Returns:
        ExternalCounter seleccionado o None si no aplica contador externo.
    """
    if explicit_counter_id:
        counter = database.session.get(ExternalCounter, explicit_counter_id)
        if not counter:
            raise IdentifierConfigurationError("El contador externo indicado no existe.")
        if not counter.is_active:
            raise IdentifierConfigurationError("El contador externo indicado esta inactivo.")
        return counter

    ctx = context or {}

    mappings = (
        database.session.execute(
            database.select(SeriesExternalCounterMap)
            .filter_by(naming_series_id=naming_series_id)
            .order_by(SeriesExternalCounterMap.priority.asc())
        )
        .scalars()
        .all()
    )

    if not mappings:
        return None

    # Separar candidatos con condicion y sin condicion
    matched_with_condition: list[tuple[SeriesExternalCounterMap, int]] = []
    fallback: SeriesExternalCounterMap | None = None

    for mapping in mappings:
        counter = database.session.get(ExternalCounter, mapping.external_counter_id)
        if not counter or not counter.is_active:
            continue
        if not mapping.condition_json:
            if fallback is None:
                fallback = mapping
        elif _condition_matches(mapping.condition_json, ctx):
            try:
                num_conditions = len(json.loads(mapping.condition_json))
            except (json.JSONDecodeError, ValueError):
                num_conditions = 0
            matched_with_condition.append((mapping, num_conditions))

    # Priorizar el candidato con mas condiciones coincidentes (mas especifico)
    if matched_with_condition:
        best = sorted(matched_with_condition, key=lambda x: -x[1])[0][0]
        return database.session.get(ExternalCounter, best.external_counter_id)

    if fallback:
        return database.session.get(ExternalCounter, fallback.external_counter_id)

    return None


# -------------------------------------------------------------------------------------
# Asignacion de identificador completo (interno + externo)
# -------------------------------------------------------------------------------------


def assign_document_identifier(
    *,
    document: object,
    entity_type: str,
    posting_date_raw: date | str | None,
    naming_series_id: str | None,
    external_counter_id: str | None = None,
    external_number: str | None = None,
    external_context: dict | None = None,
    allow_closing: bool = False,
) -> None:
    """Asigna document_no, naming_series_id y (opcionalmente) external_number a un documento.

    El flujo completo es:
    1. Validar y normalizar posting_date.
    2. Validar periodo contable no cerrado.
    3. Seleccionar NamingSeries activa.
    4. Generar identificador interno (document_no).
    5. Resolver contador externo si aplica (serie tiene mapeo o se indica explicitamente).
    6. Validar unicidad del numero externo.
    7. Persistir external_counter_id + external_number en el documento.
    8. Registrar uso en ExternalNumberUsage + actualizar last_used.

    Args:
        document: Objeto ORM con campos company, id, posting_date, document_no, etc.
        entity_type: Tipo de entidad (ej: 'payment_entry')
        posting_date_raw: Fecha de contabilizacion (date, str ISO o None)
        naming_series_id: ID de NamingSeries explicitamente seleccionada (o None para autoseleccion)
        external_counter_id: ID de ExternalCounter explicitamente seleccionado (o None)
        external_number: Numero externo fisico a usar (o None para usar el sugerido por el contador)
        external_context: Contexto adicional para seleccion contextual de contador (payment_method, etc.)
        allow_closing: Permite asignar identificador en periodos cerrados si es comprobante de cierre.
    """
    posting_date = parse_posting_date(posting_date_raw)
    company = getattr(document, "company", None)
    validate_accounting_period(company=company, posting_date=posting_date, allow_closing=allow_closing)
    company_code = cast(str, company)

    # 1. Identificador interno
    naming_series = _pick_naming_series(
        entity_type=entity_type,
        company=company_code,
        naming_series_id=naming_series_id,
    )
    sequence_id = _pick_sequence_id(naming_series.id)

    identifier = generate_identifier(
        entity_type=entity_type,
        entity_id=getattr(document, "id"),
        posting_date=posting_date,
        company=company_code,
        naming_series_id=naming_series.id,
        sequence_id=sequence_id,
    )

    setattr(document, "posting_date", posting_date)
    setattr(document, "naming_series_id", naming_series.id)
    setattr(document, "document_no", identifier)

    # 2. Identificador externo (opcional)
    counter = _resolve_external_counter(
        naming_series_id=naming_series.id,
        context=external_context,
        explicit_counter_id=external_counter_id,
    )

    if counter:
        if counter.company != company_code:
            raise IdentifierConfigurationError("El contador externo no pertenece a la compania indicada.")
        ext_num = external_number or counter.next_suggested_formatted
        _validate_and_register_external_number(
            counter=counter,
            external_number=ext_num,
            entity_type=entity_type,
            entity_id=getattr(document, "id"),
        )
        setattr(document, "external_counter_id", counter.id)
        setattr(document, "external_number", ext_num)


def _validate_and_register_external_number(
    *,
    counter: ExternalCounter,
    external_number: str,
    entity_type: str,
    entity_id: str,
) -> None:
    """Valida unicidad y registra el uso de un numero externo.

    Raises:
        ExternalNumberDuplicateError: Si el numero ya fue utilizado con este contador.
    """
    existing = database.session.execute(
        database.select(ExternalNumberUsage).filter_by(
            external_counter_id=counter.id,
            external_number=external_number,
        )
    ).scalar_one_or_none()

    if existing:
        raise ExternalNumberDuplicateError(
            f"El numero externo '{external_number}' ya fue utilizado en este contador "
            f"por el documento {existing.entity_type}/{existing.entity_id}."
        )

    # Intentar extraer el valor numerico del numero externo (despues del prefijo)
    prefix = counter.prefix or ""
    prefix_len = len(prefix)
    raw = external_number[prefix_len:]
    try:
        sequence_value = int(raw)
    except ValueError:
        sequence_value = None

    usage = ExternalNumberUsage(
        external_counter_id=counter.id,
        external_number=external_number,
        entity_type=entity_type,
        entity_id=entity_id,
        sequence_value=sequence_value,
    )
    database.session.add(usage)

    # Actualizar last_used si el valor numerico es mayor al actual
    if sequence_value is not None and sequence_value > (counter.last_used or 0):
        counter.last_used = sequence_value

    database.session.flush()


# -------------------------------------------------------------------------------------
# External Counter Services (ajuste manual con auditoria)
# -------------------------------------------------------------------------------------


def suggest_next_external_number(external_counter_id: str) -> str:
    """Devuelve el siguiente numero externo sugerido para un contador externo.

    Args:
        external_counter_id: ID del ExternalCounter

    Returns:
        Cadena con el numero sugerido (prefijo + numero formateado con padding)

    Raises:
        IdentifierConfigurationError: Si el contador no existe o esta inactivo
    """
    counter = database.session.get(ExternalCounter, external_counter_id)
    if not counter:
        raise IdentifierConfigurationError(EL_CONTADOR_EXTERNO_NO_EXISTE)
    if not counter.is_active:
        raise IdentifierConfigurationError(EL_CONTADOR_EXTERNO_ESTA_INACTIVO)
    return counter.next_suggested_formatted


def record_external_number_used(
    *,
    external_counter_id: str,
    number_used: int,
    changed_by: str | None = None,
) -> None:
    """Registra el uso de un numero externo incrementando last_used si corresponde.

    Actualiza last_used solo si number_used es mayor al valor actual.

    Args:
        external_counter_id: ID del ExternalCounter
        number_used: Numero externo utilizado en el documento
        changed_by: ID del usuario que realiza el registro
    """
    counter = database.session.get(ExternalCounter, external_counter_id)
    if not counter:
        raise IdentifierConfigurationError(EL_CONTADOR_EXTERNO_NO_EXISTE)
    if not counter.is_active:
        raise IdentifierConfigurationError(EL_CONTADOR_EXTERNO_ESTA_INACTIVO)
    if number_used < 0:
        raise IdentifierConfigurationError("El numero externo usado no puede ser negativo.")

    if number_used > (counter.last_used or 0):
        counter.last_used = number_used
        database.session.flush()


def adjust_external_counter(
    *,
    external_counter_id: str,
    new_last_used: int,
    reason: str,
    changed_by: str | None = None,
) -> None:
    """Ajusta el ultimo numero usado de un contador externo con auditoria obligatoria.

    Esta operacion exige un motivo explicito. Cada ajuste queda registrado
    en ExternalCounterAuditLog con el valor anterior, el nuevo valor, el usuario
    y la fecha del cambio.

    Args:
        external_counter_id: ID del ExternalCounter a ajustar
        new_last_used: Nuevo valor para last_used
        reason: Motivo obligatorio del ajuste (no puede estar vacio)
        changed_by: ID del usuario que realiza el ajuste

    Raises:
        IdentifierConfigurationError: Si el contador no existe, esta inactivo
                                      o el motivo esta vacio
    """
    if not reason or not reason.strip():
        raise IdentifierConfigurationError("Debe indicar el motivo del ajuste del contador externo.")
    if new_last_used < 0:
        raise IdentifierConfigurationError("El ultimo numero usado no puede ser negativo.")

    counter = database.session.get(ExternalCounter, external_counter_id)
    if not counter:
        raise IdentifierConfigurationError(EL_CONTADOR_EXTERNO_NO_EXISTE)
    if not counter.is_active:
        raise IdentifierConfigurationError(EL_CONTADOR_EXTERNO_ESTA_INACTIVO)

    previous_value = counter.last_used or 0

    audit_entry = ExternalCounterAuditLog(
        external_counter_id=counter.id,
        previous_value=previous_value,
        new_value=new_last_used,
        reason=reason.strip(),
        changed_by=changed_by,
    )
    database.session.add(audit_entry)
    counter.last_used = new_last_used
    database.session.flush()
