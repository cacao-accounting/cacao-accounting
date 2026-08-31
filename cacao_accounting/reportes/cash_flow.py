# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Estado de Flujo de Efectivo (NIC 7, método indirecto).

El reporte es una proyección determinista del libro mayor: la utilidad del
período se ajusta por el movimiento de las cuentas de balance clasificadas
explícitamente en :class:`~cacao_accounting.database.CashFlowAccountMapping`.
No existe clasificación automática silenciosa: si una cuenta con movimiento
en el período carece de mapeo explícito, el reporte se bloquea y se solicita
completar la configuración en su vista dedicada.

Por identidad contable, con cobertura completa se cumple exactamente::

    variación_neta_calculada = utilidad + ajustes_operación + inversión + financiamiento
    variación_neta_reportada = saldo_final_efectivo - saldo_inicial_efectivo
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from cacao_accounting.database import (
    Accounts,
    Book,
    CashFlowAccountMapping,
    GLEntry,
    database,
)

try:  # pragma: no cover - fallback defensivo para contextos sin Flask-Babel inicializado.
    from flask_babel import gettext as _babel_gettext
except ImportError:  # pragma: no cover

    def _(value: str) -> str:
        return value

else:

    def _(value: str) -> str:
        try:
            return _babel_gettext(value)
        except (KeyError, RuntimeError):
            return value


SECTION_OPERATING = "operating"
SECTION_INVESTING = "investing"
SECTION_FINANCING = "financing"
SECTION_CASH = "cash"

VALID_SECTIONS = (SECTION_OPERATING, SECTION_INVESTING, SECTION_FINANCING, SECTION_CASH)


def _period_bounds_for(
    company: str,
    accounting_period: str | None,
    period_from: str | None = None,
    period_to: str | None = None,
) -> tuple[Any, Any, Any]:
    """Resuelve los límites del período contable o del rango seleccionado."""
    from cacao_accounting.reportes.services import _period_bounds, _report_period_bounds

    if not (period_from or period_to):
        return _period_bounds(company, accounting_period)

    class _FiltersProxy:
        """Proxy mínimo que expone el contrato que ``_report_period_bounds`` espera."""

        __slots__ = ("company", "accounting_period", "period_from", "period_to")
        company: str
        accounting_period: str | None
        period_from: str | None
        period_to: str | None

    proxy = _FiltersProxy()
    proxy.company = company
    proxy.accounting_period = accounting_period
    proxy.period_from = period_from
    proxy.period_to = period_to
    return _report_period_bounds(proxy)


#: Etiquetas visibles de las secciones para la vista dedicada de configuración.
SECTION_LABELS = {
    SECTION_OPERATING: _("Operación"),
    SECTION_INVESTING: _("Inversión"),
    SECTION_FINANCING: _("Financiamiento"),
    SECTION_CASH: _("Efectivo y equivalentes"),
}

#: Clasificaciones de estado de resultados: alimentan la utilidad y no exigen mapeo.
_PL_CLASSIFICATIONS = frozenset({"ingreso", "income", "costo", "cost", "gasto", "expense"})

#: Sugerencia visual por ``account_type`` del catálogo. Nunca es efectiva sin
#: guardar el mapeo explícito; solo preselecciona el valor en la vista dedicada.
_SUGGESTION_BY_ACCOUNT_TYPE: dict[str, str] = {
    "cash": SECTION_CASH,
    "bank": SECTION_CASH,
    "receivable": SECTION_OPERATING,
    "inventory": SECTION_OPERATING,
    "payable": SECTION_OPERATING,
    "tax": SECTION_OPERATING,
    "customer_advance": SECTION_OPERATING,
    "supplier_advance": SECTION_OPERATING,
    "deferred_income": SECTION_OPERATING,
    "deferred_expense": SECTION_OPERATING,
    "bridge": SECTION_OPERATING,
    "asset": SECTION_INVESTING,
    "liability": SECTION_FINANCING,
    "equity": SECTION_FINANCING,
    "retained_earnings": SECTION_FINANCING,
}

_ALIASES = {
    "activos": "activo",
    "pasivos": "pasivo",
    "ingresos": "ingreso",
    "costos": "costo",
    "gastos": "gasto",
    "assets": "asset",
    "liabilities": "liability",
    "equities": "equity",
}


@dataclass(frozen=True)
class CashFlowConfigurationStatus:
    """Cobertura de configuración del EFE para una selección compañía/libro/período."""

    pending_accounts: list[dict[str, Any]] = field(default_factory=list)
    has_cash_accounts: bool = False

    @property
    def complete(self) -> bool:
        """True cuando no faltan cuentas por clasificar y existe al menos una cuenta de efectivo."""
        return not self.pending_accounts and self.has_cash_accounts


@dataclass
class CashFlowMovementTotals:
    """Acumuladores de movimientos usados para construir el estado de flujo."""

    section_totals: dict[str, Decimal]
    section_details: dict[str, dict[str, dict[str, Any]]]
    net_profit: Decimal = Decimal("0")
    cash_window_delta: Decimal = Decimal("0")
    cash_opening: Decimal = Decimal("0")


def normalize_classification(classification: str | None) -> str:
    """Normaliza la clasificación de una cuenta para el motor del EFE."""
    raw = (classification or "").strip().lower()
    return _ALIASES.get(raw, raw)


def suggest_section(account: Accounts) -> str | None:
    """Sugerencia visual de sección NIC 7 para la vista de configuración.

    Se basa en ``account_type`` y como respaldo en la clasificación contable.
    El resultado nunca configura nada por sí mismo: solo preselecciona el
    valor del formulario hasta que el usuario guarda el mapeo explícito.
    """
    suggestion = _SUGGESTION_BY_ACCOUNT_TYPE.get((account.account_type or "").strip().lower())
    if suggestion:
        return suggestion
    classification = normalize_classification(account.classification)
    if classification in {"activo", "asset"}:
        return SECTION_INVESTING
    if classification in {"pasivo", "liability", "patrimonio", "equity"}:
        return SECTION_FINANCING
    return None


def load_cash_flow_mappings(company: str) -> dict[str, str]:
    """Devuelve el mapeo explícito cuenta→sección de una compañía."""
    rows = database.session.execute(
        select(CashFlowAccountMapping.account_id, CashFlowAccountMapping.flow_section).where(
            CashFlowAccountMapping.company == company
        )
    ).all()
    return {account_id: section for account_id, section in rows}


def save_cash_flow_mappings(company: str, overrides: dict[str, str | None]) -> None:
    """Guarda o elimina mapeos explícitos de cuentas para una compañía.

    Un valor vacío o ``None`` elimina el mapeo existente (vuelve a pendiente).
    Lanza ``ValueError`` ante secciones o cuentas desconocidas para impedir
    configuraciones inválidas desde la vista dedicada.
    """
    clean: dict[str, str] = {}
    for account_id, raw_section in overrides.items():
        section = (raw_section or "").strip().lower()
        if not section:
            continue
        if section not in VALID_SECTIONS:
            raise ValueError(f"Sección de flujo inválida: {section}")
        account = database.session.execute(
            select(Accounts).where(Accounts.id == account_id, Accounts.entity == company)
        ).scalar_one_or_none()
        if account is None:
            raise ValueError("La cuenta indicada no pertenece a la compañía.")
        clean[account_id] = section

    existing = {
        account_id: mapping
        for account_id, mapping in database.session.execute(
            select(CashFlowAccountMapping.account_id, CashFlowAccountMapping).where(CashFlowAccountMapping.company == company)
        ).all()
    }
    for account_id, mapping in existing.items():
        target = clean.get(account_id)
        if target is None:
            database.session.delete(mapping)
        elif target != mapping.flow_section:
            mapping.flow_section = target
    for account_id, section in clean.items():
        if account_id not in existing:
            database.session.add(CashFlowAccountMapping(company=company, account_id=account_id, flow_section=section))


def _movement_scope_filters(company: str, ledger: Book, period_start: Any, period_end: Any) -> list[Any]:
    """Filtros comunes del alcance contable del EFE.

    Excluye anulados, reversas y comprobantes de cierre fiscal: mismas bases
    de la balanza de comprobación por defecto, de modo que la utilidad y los
    movimientos de balance provengan del mismo universo de líneas.
    """
    filters = [
        GLEntry.company == company,
        GLEntry.ledger_id == ledger.id,
        GLEntry.is_cancelled.is_(False),
        GLEntry.is_reversal.is_(False),
        GLEntry.is_fiscal_year_closing.is_(False),
    ]
    if period_start:
        filters.append(GLEntry.posting_date >= period_start)
    if period_end:
        filters.append(GLEntry.posting_date <= period_end)
    return filters


def _moving_accounts(company: str, ledger: Book, period_start: Any, period_end: Any) -> list[tuple[Accounts, Any]]:
    """Cuentas con movimiento neto distinto de cero dentro de la ventana."""
    rows = database.session.execute(
        select(Accounts, GLEntry.debit - GLEntry.credit)
        .join(GLEntry, GLEntry.account_id == Accounts.id)
        .where(*_movement_scope_filters(company, ledger, period_start, period_end))
    ).all()
    deltas: dict[str, Decimal] = {}
    by_account: dict[str, Accounts] = {}
    for account, delta in rows:
        by_account[account.id] = account
        deltas[account.id] = deltas.get(account.id, Decimal("0")) + Decimal(str(delta or "0"))
    return [(by_account[account_id], delta) for account_id, delta in deltas.items() if delta != 0]


def get_cash_flow_configuration_status(
    company: str,
    ledger: str | None,
    accounting_period: str | None,
    period_from: str | None = None,
    period_to: str | None = None,
) -> CashFlowConfigurationStatus:
    """Valida la cobertura del mapeo antes de permitir generar el reporte.

    Una cuenta requiere clasificación cuando tiene movimiento neto en la
    ventana y su clasificación es de balance o está indefinida; las cuentas
    de resultados alimentan la utilidad y quedan exentas. Además debe existir
    al menos una cuenta clasificada como efectivo para poder medir la
    variación que el reporte debe cuadrar.
    """
    from cacao_accounting.reportes.services import _resolve_ledger

    resolved_ledger = _resolve_ledger(company, ledger)
    if resolved_ledger is None:
        return CashFlowConfigurationStatus(pending_accounts=[], has_cash_accounts=False)
    period_start, period_end, _period = _period_bounds_for(company, accounting_period, period_from, period_to)
    mappings = load_cash_flow_mappings(company)
    pending = []
    for account, _delta in _moving_accounts(company, resolved_ledger, period_start, period_end):
        section = mappings.get(account.id)
        if section == SECTION_CASH:
            continue
        classification = normalize_classification(account.classification)
        if classification in _PL_CLASSIFICATIONS:
            continue
        if section is None:
            pending.append({"code": account.code or "", "name": account.name or "", "id": account.id})
    has_cash = SECTION_CASH in mappings.values()
    pending.sort(key=lambda item: item["code"])
    return CashFlowConfigurationStatus(pending_accounts=pending, has_cash_accounts=has_cash)


def _cash_flow_movement_totals(
    filters: Any,
    period_start: Any,
    period_end: Any,
    mappings: dict[str, str],
) -> CashFlowMovementTotals:
    """Acumula utilidad, efectivo y movimientos clasificados por sección."""
    from cacao_accounting.reportes.services import _decimal_value, _resolve_ledger

    ledger = _resolve_ledger(filters.company, filters.ledger)
    totals = CashFlowMovementTotals(
        section_totals={
            SECTION_OPERATING: Decimal("0"),
            SECTION_INVESTING: Decimal("0"),
            SECTION_FINANCING: Decimal("0"),
        },
        section_details={section: {} for section in (SECTION_OPERATING, SECTION_INVESTING, SECTION_FINANCING)},
    )
    if ledger is None:  # pragma: no cover - la validación previa ya resuelve el libro
        return totals

    query = (
        select(GLEntry, Accounts)
        .join(Accounts, Accounts.id == GLEntry.account_id, isouter=True)
        .where(*_movement_scope_filters(filters.company, ledger, None, period_end))
    )
    for entry, account in database.session.execute(query).all():
        if account is None:
            continue
        delta = _decimal_value(entry.debit) - _decimal_value(entry.credit)
        before_start = bool(period_start) and entry.posting_date < period_start
        if before_start:
            if mappings.get(account.id) == SECTION_CASH:
                totals.cash_opening += delta
            continue
        if mappings.get(account.id) == SECTION_CASH:
            totals.cash_window_delta += delta
            continue
        classification = normalize_classification(account.classification)
        if classification in {"ingreso", "income"}:
            totals.net_profit += _decimal_value(entry.credit) - _decimal_value(entry.debit)
            continue
        if classification in {"costo", "cost", "gasto", "expense"}:
            totals.net_profit -= delta
            continue
        section = mappings.get(account.id)
        if section not in totals.section_totals:
            continue
        contribution = -delta
        totals.section_totals[section] += contribution
        detail = totals.section_details[section].setdefault(
            account.id,
            {
                "account_code": account.code or "",
                "account_name": account.name or "",
                "amount": Decimal("0"),
                "level": (account.code or "").count(".") + 1,
            },
        )
        detail["amount"] += contribution
    return totals


def _cash_flow_detail_rows(section: str, details: dict[str, dict[str, Any]]) -> list[Any]:
    """Convierte los detalles no nulos de una sección en filas del reporte."""
    from cacao_accounting.reportes.services import ReportRow

    return [
        ReportRow(
            {
                "section": section,
                "account_code": values["account_code"],
                "account_name": values["account_name"],
                "amount": values["amount"],
                "level": values["level"],
            }
        )
        for values in sorted(details.values(), key=lambda item: str(item["account_code"]))
        if values["amount"] != Decimal("0")
    ]


def get_cash_flow_statement(filters: Any) -> Any:
    """Estado de Flujo de Efectivo por método indirecto (NIC 7).

    Devuelve un :class:`PaginatedReport` con las secciones operación,
    inversión y financiamiento, la variación neta calculada y los saldos de
    efectivo inicial y final del libro seleccionado. ``totals["difference"]``
    contiene la brecha entre la variación calculada y la observada en las
    cuentas de efectivo; con configuración completa debe ser cero.

    Lanza ``ValueError`` si la configuración de mapeo está incompleta: la
    ruta valida previamente para presentar el estado de bloqueo, este control
    es la barrera defensiva para cualquier otro llamador.
    """
    from cacao_accounting.reportes.services import (
        FinancialReportFilters,
        PaginatedReport,
        ReportRow,
        _report_period_bounds,
        _resolve_ledger,
    )

    if not isinstance(filters, FinancialReportFilters):  # pragma: no cover - contrato interno
        raise TypeError("get_cash_flow_statement espera FinancialReportFilters")
    status = get_cash_flow_configuration_status(
        filters.company,
        filters.ledger,
        filters.accounting_period,
        getattr(filters, "period_from", None),
        getattr(filters, "period_to", None),
    )
    if not status.complete:
        raise ValueError(_("La configuración del flujo de efectivo está incompleta."))

    period_start, period_end, _period = _report_period_bounds(filters)
    ledger = _resolve_ledger(filters.company, filters.ledger)
    if ledger is None:  # pragma: no cover - la validación previa ya resuelve el libro
        return PaginatedReport(rows=[], totals={}, columns=[])

    mappings = load_cash_flow_mappings(filters.company)
    movement_totals = _cash_flow_movement_totals(filters, period_start, period_end, mappings)
    section_totals = movement_totals.section_totals
    section_details = movement_totals.section_details
    net_profit = movement_totals.net_profit
    cash_window_delta = movement_totals.cash_window_delta
    cash_opening = movement_totals.cash_opening

    operating_total = section_totals[SECTION_OPERATING]
    rows: list[Any] = [
        ReportRow({"section": "net_profit", "account_code": None, "account_name": None, "amount": net_profit, "level": 0}),
        ReportRow(
            {
                "section": "operating_adjustments",
                "account_code": None,
                "account_name": None,
                "amount": operating_total,
                "level": 0,
            }
        ),
        *_cash_flow_detail_rows(SECTION_OPERATING, section_details[SECTION_OPERATING]),
        ReportRow(
            {
                "section": "total_operating",
                "account_code": None,
                "account_name": None,
                "amount": net_profit + operating_total,
                "level": 0,
            }
        ),
        ReportRow(
            {
                "section": "investing",
                "account_code": None,
                "account_name": None,
                "amount": section_totals[SECTION_INVESTING],
                "level": 0,
            }
        ),
        *_cash_flow_detail_rows(SECTION_INVESTING, section_details[SECTION_INVESTING]),
        ReportRow(
            {
                "section": "total_investing",
                "account_code": None,
                "account_name": None,
                "amount": section_totals[SECTION_INVESTING],
                "level": 0,
            }
        ),
        ReportRow(
            {
                "section": "financing",
                "account_code": None,
                "account_name": None,
                "amount": section_totals[SECTION_FINANCING],
                "level": 0,
            }
        ),
        *_cash_flow_detail_rows(SECTION_FINANCING, section_details[SECTION_FINANCING]),
        ReportRow(
            {
                "section": "total_financing",
                "account_code": None,
                "account_name": None,
                "amount": section_totals[SECTION_FINANCING],
                "level": 0,
            }
        ),
    ]
    net_change_calculated = (
        net_profit + operating_total + section_totals[SECTION_INVESTING] + section_totals[SECTION_FINANCING]
    )
    cash_closing = cash_opening + cash_window_delta
    reported_variation = cash_window_delta
    rows.extend(
        [
            ReportRow(
                {
                    "section": "net_change_cash",
                    "account_code": None,
                    "account_name": None,
                    "amount": net_change_calculated,
                    "level": 0,
                }
            ),
            ReportRow(
                {"section": "cash_opening", "account_code": None, "account_name": None, "amount": cash_opening, "level": 0}
            ),
            ReportRow(
                {"section": "cash_closing", "account_code": None, "account_name": None, "amount": cash_closing, "level": 0}
            ),
        ]
    )
    return PaginatedReport(
        rows=rows,
        totals={
            "net_profit": net_profit,
            "operating": net_profit + operating_total,
            "operating_adjustments": operating_total,
            "investing": section_totals[SECTION_INVESTING],
            "financing": section_totals[SECTION_FINANCING],
            "net_change_cash": net_change_calculated,
            "cash_opening": cash_opening,
            "cash_closing": cash_closing,
            "difference": net_change_calculated - reported_variation,
        },
        columns=["section", "account_code", "account_name", "amount", "level"],
        total_rows=len(rows),
        page=1,
        page_size=max(len(rows), 1),
        ledger_currency=ledger.currency,
    )


def get_cash_flow_config_overview(company: str) -> dict[str, Any]:
    """Datos de la vista dedicada de clasificación NIC 7 por compañía.

    Combina el catálogo activo no agrupador con el mapeo vigente, marca las
    cuentas con movimiento histórico y prioriza las pendientes con movimiento;
    incluye el conteo de cobertura para el indicador de desbloqueo del EFE.
    """
    accounts_list = (
        database.session.execute(
            select(Accounts).where(
                Accounts.entity == company,
                Accounts.active.is_(True),
                Accounts.group.is_(None) | Accounts.group.is_(False),
            )
        )
        .scalars()
        .all()
    )
    mappings = load_cash_flow_mappings(company)
    accounts_with_movement = {
        row[0]
        for row in database.session.execute(
            select(GLEntry.account_id).distinct().where(GLEntry.company == company, GLEntry.is_cancelled.is_(False))
        ).all()
        if row[0]
    }
    rows = [
        {
            "id": account.id,
            "code": account.code or "",
            "name": account.name or "",
            "classification": normalize_classification(account.classification) or "",
            "account_type": account.account_type or "",
            "suggestion": suggest_section(account),
            "section": mappings.get(account.id),
            "has_movement": account.id in accounts_with_movement,
        }
        for account in accounts_list
    ]
    rows.sort(key=lambda item: (item["section"] is not None, not item["has_movement"], item["code"]))
    mapped_count = sum(1 for row in rows if row["section"])
    return {
        "rows": rows,
        "mapped_count": mapped_count,
        "pending_count": sum(1 for row in rows if row["section"] is None and row["has_movement"]),
        "sections": VALID_SECTIONS,
    }
