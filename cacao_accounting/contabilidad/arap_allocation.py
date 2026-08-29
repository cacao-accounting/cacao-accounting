# SPDX-License-Identifier: Apache-2.0
"""Motor reutilizable para resolver, planear y aplicar asignaciones AR/AP.

Los montos de las solicitudes están en la moneda documental. La tasa expresa
cuánto efectivo de la moneda origen consume una unidad documental. La
persistencia se delega a un callback para compartir reglas entre pagos y
referencias de diarios, manteniendo el control de la transacción en el flujo
que la invoca.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable

from sqlalchemy import func, select

from cacao_accounting.database import ARAPLedgerEntry, ARAPOpenItem as ARAPOpenItemModel, database


class AllocationError(ValueError):
    """Error de negocio al resolver, planear o aplicar una asignación."""


class AllocationCurrencyError(AllocationError):
    """La moneda o la tasa necesaria no es válida."""


class AllocationOverpaymentError(AllocationError):
    """La asignación excede el saldo documental o efectivo disponible."""


class AllocationIdempotencyError(AllocationError):
    """Una clave existente se intentó reutilizar con otro importe."""


def _decimal(value: Any) -> Decimal:
    """Convierte un monto a ``Decimal`` sin cálculos binarios."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AllocationError(f"Monto inválido: {value!r}.") from exc


@dataclass(frozen=True)
class ARAPOpenItem:
    """Documento con saldo pendiente en moneda documental."""

    document_id: str
    document_type: str
    currency: str
    outstanding: Decimal
    company: str | None = None
    document_no: str | None = None
    economic_line_id: str | None = None
    account_id: str | None = None
    party_type: str | None = None
    party_id: str | None = None
    ledger_type: str | None = None
    posting_date: Any = None
    direction: str | None = None
    open_item_id: str | None = None
    line_number: int | None = None

    def __post_init__(self) -> None:
        """Valida identificadores y saldo no negativo."""
        amount = _decimal(self.outstanding)
        if not self.document_id or not self.document_type or not self.currency:
            raise AllocationError("Un open item requiere documento y moneda explícitos.")
        if amount < 0:
            raise AllocationError("El saldo pendiente no puede ser negativo.")
        object.__setattr__(self, "outstanding", amount)
        if self.direction is not None and self.direction not in {"debit", "credit"}:
            raise AllocationError("La dirección del open item debe ser debit o credit.")

    @classmethod
    def from_model(cls, model: Any) -> "ARAPOpenItem":
        """Convierte una fila ``database.ARAPOpenItem`` a DTO de dominio."""
        return cls(
            document_id=str(model.document_id),
            document_type=str(model.document_type),
            currency=str(model.currency),
            outstanding=_decimal(getattr(model, "unallocated_amount", 0)),
            company=getattr(model, "company", None),
            document_no=getattr(model, "document_no", None),
            economic_line_id=getattr(model, "economic_line_id", None),
            account_id=getattr(model, "account_id", None),
            party_type=getattr(model, "party_type", None),
            party_id=getattr(model, "party_id", None),
            ledger_type=getattr(model, "ledger_type", None),
            posting_date=getattr(model, "posting_date", None),
            direction=getattr(model, "direction", None),
            open_item_id=getattr(model, "id", None),
            line_number=getattr(model, "line_number", None),
        )


# Nombre corto para consumidores que no necesitan distinguir otros subledgers.
OpenItem = ARAPOpenItem


@dataclass(frozen=True)
class AllocationRequest:
    """Solicitud de aplicar ``amount`` en la moneda del documento."""

    document_id: str
    amount: Decimal | None = None
    rate: Decimal | None = None
    idempotency_key: str | None = None


# Alias explícito para consumidores que distinguen la solicitud de su línea resultante.
AllocationLineRequest = AllocationRequest


@dataclass(frozen=True)
class AllocationLine:
    """Línea validada lista para persistirse como movimiento append-only."""

    document_id: str
    document_type: str
    document_currency: str
    source_currency: str
    document_amount: Decimal
    source_amount: Decimal
    rate: Decimal
    idempotency_key: str | None = None


@dataclass(frozen=True)
class AllocationPlan:
    """Plan validado sin modificar saldos."""

    source_currency: str
    source_amount: Decimal
    lines: tuple[AllocationLine, ...]

    @property
    def allocated_source_amount(self) -> Decimal:
        """Total de efectivo consumido por el plan."""
        return sum((line.source_amount for line in self.lines), Decimal("0"))

    @property
    def remaining_source_amount(self) -> Decimal:
        """Efectivo no asignado."""
        return self.source_amount - self.allocated_source_amount

    @property
    def is_full(self) -> bool:
        """Indica si el plan consume todo el efectivo disponible."""
        return self.remaining_source_amount == 0


class OpenItemResolver:
    """Índice transaccional de documentos y saldos abiertos."""

    def __init__(self, items: Iterable[ARAPOpenItem] = ()) -> None:
        """Inicializa el índice y rechaza documentos duplicados."""
        self._items: dict[str, ARAPOpenItem] = {}
        self._applied: dict[str, AllocationLine] = {}
        for item in items:
            self.add(item)

    @staticmethod
    def _key(item: ARAPOpenItem) -> str:
        """Build a stable in-memory key without exposing a synthetic database ID."""
        return item.open_item_id or (
            f"{item.document_id}:{item.economic_line_id}" if item.economic_line_id else item.document_id
        )

    @classmethod
    def from_ledger(cls, **filters: Any) -> "OpenItemResolver":
        """Construye un resolver leyendo saldos reconstruidos del ledger."""
        return cls(list_open_items(**filters))

    @classmethod
    def from_models(cls, models: Iterable[Any]) -> "OpenItemResolver":
        """Construye un resolver desde filas ORM de ``ARAPOpenItem``."""
        return cls(ARAPOpenItem.from_model(model) for model in models)

    def add(self, item: ARAPOpenItem) -> None:
        """Añade un documento al índice."""
        key = self._key(item)
        if key in self._items:
            raise AllocationError(f"El documento {item.document_id} está duplicado.")
        self._items[key] = item

    def resolve(self, document_id: str) -> ARAPOpenItem:
        """Obtiene un documento por id."""
        exact = self._items.get(document_id)
        if exact is not None:
            return exact
        matches = [item for item in self._items.values() if item.document_id == document_id]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise AllocationError(f"El documento {document_id} tiene varias líneas abiertas; indique el open item.")
        raise AllocationError(f"No existe open item para {document_id}.")

    def all(self) -> tuple[ARAPOpenItem, ...]:
        """Devuelve una instantánea de los documentos indexados."""
        return tuple(self._items.values())

    def consume(self, document_id: str, amount: Decimal) -> None:
        """Consume saldo después de persistir una línea."""
        item = self.resolve(document_id)
        key = self._key(item)
        amount = _decimal(amount)
        if amount <= 0 or amount > item.outstanding:
            raise AllocationOverpaymentError(f"La asignación excede el saldo de {document_id}.")
        self._items[key] = ARAPOpenItem(
            document_id=item.document_id,
            document_type=item.document_type,
            currency=item.currency,
            outstanding=item.outstanding - amount,
            company=item.company,
            document_no=item.document_no,
            economic_line_id=item.economic_line_id,
            account_id=item.account_id,
            party_type=item.party_type,
            party_id=item.party_id,
            ledger_type=item.ledger_type,
            posting_date=item.posting_date,
            direction=item.direction,
            open_item_id=item.open_item_id,
            line_number=item.line_number,
        )

    def snapshot(self) -> dict[str, ARAPOpenItem]:
        """Captura el índice para rollback."""
        return dict(self._items)

    def restore(self, snapshot: dict[str, ARAPOpenItem]) -> None:
        """Restaura un snapshot anterior."""
        self._items = dict(snapshot)


def list_open_items(
    *,
    company: str | None = None,
    party_type: str | None = None,
    party_id: str | None = None,
    currency: str | None = None,
    as_of_date: Any = None,
    session: Any = None,
) -> tuple[ARAPOpenItem, ...]:
    """Reconstruye open items desde el ledger documental hasta una fecha."""
    db_session = session or database.session
    query = select(
        ARAPLedgerEntry.document_id,
        ARAPLedgerEntry.document_type,
        ARAPLedgerEntry.currency,
        ARAPLedgerEntry.company,
        ARAPLedgerEntry.party_type,
        ARAPLedgerEntry.party_id,
        ARAPLedgerEntry.ledger_type,
        ARAPLedgerEntry.economic_line_id,
        func.sum(ARAPLedgerEntry.document_amount).label("outstanding"),
        func.max(ARAPLedgerEntry.posting_date).label("posting_date"),
    ).group_by(
        ARAPLedgerEntry.document_id,
        ARAPLedgerEntry.document_type,
        ARAPLedgerEntry.currency,
        ARAPLedgerEntry.company,
        ARAPLedgerEntry.party_type,
        ARAPLedgerEntry.party_id,
        ARAPLedgerEntry.ledger_type,
        ARAPLedgerEntry.economic_line_id,
    )
    if company is not None:
        query = query.where(ARAPLedgerEntry.company == company)
    if party_type is not None:
        query = query.where(ARAPLedgerEntry.party_type == party_type)
    if party_id is not None:
        query = query.where(ARAPLedgerEntry.party_id == party_id)
    if currency is not None:
        query = query.where(ARAPLedgerEntry.currency == currency)
    if as_of_date is not None:
        query = query.where(ARAPLedgerEntry.posting_date <= as_of_date)
    rows = db_session.execute(query).all()
    return tuple(
        ARAPOpenItem(
            document_id=str(row.document_id),
            document_type=str(row.document_type),
            currency=str(row.currency),
            outstanding=abs(_decimal(row.outstanding)),
            company=row.company,
            document_no=None,
            economic_line_id=row.economic_line_id,
            account_id=None,
            party_type=row.party_type,
            party_id=row.party_id,
            ledger_type=row.ledger_type,
            posting_date=row.posting_date,
            direction="debit" if _decimal(row.outstanding) > 0 else "credit",
        )
        for row in rows
        if _decimal(row.outstanding) != 0
    )


def list_cached_open_items(
    *,
    company: str | None = None,
    party_type: str | None = None,
    party_id: str | None = None,
    currency: str | None = None,
    session: Any = None,
) -> tuple[ARAPOpenItem, ...]:
    """Lista snapshots positivos de ``ARAPOpenItem`` para consultas rápidas.

    El cache no reemplaza ``list_open_items`` para auditoría; esta función es
    útil en pantallas que necesitan el saldo actual sin reconstruir el ledger.
    """
    db_session = session or database.session
    query = select(ARAPOpenItemModel).where(ARAPOpenItemModel.unallocated_amount > 0)
    if company is not None:
        query = query.where(ARAPOpenItemModel.company == company)
    if party_type is not None:
        query = query.where(ARAPOpenItemModel.party_type == party_type)
    if party_id is not None:
        query = query.where(ARAPOpenItemModel.party_id == party_id)
    if currency is not None:
        query = query.where(ARAPOpenItemModel.currency == currency)
    return tuple(ARAPOpenItem.from_model(model) for model in db_session.execute(query).scalars())


def resolve_open_item(
    document_id: str,
    *,
    document_type: str | None = None,
    currency: str | None = None,
    company: str | None = None,
    as_of_date: Any = None,
    session: Any = None,
) -> ARAPOpenItem:
    """Resuelve un documento desde el ledger y exige saldo positivo único."""
    items = list_open_items(company=company, currency=currency, as_of_date=as_of_date, session=session)
    matches = [
        item
        for item in items
        if item.document_id == document_id and (document_type is None or item.document_type == document_type)
    ]
    if len(matches) != 1:
        raise AllocationError(f"No existe un open item único para {document_id}.")
    return matches[0]


class AllocationPlanner:
    """Valida monedas, saldos e importes antes de ejecutar."""

    def __init__(self, resolver: OpenItemResolver) -> None:
        """Asocia el planificador a un resolver."""
        self.resolver = resolver

    def plan(
        self,
        source_amount: Decimal,
        source_currency: str,
        requests: Iterable[AllocationRequest],
        *,
        existing_keys: Iterable[str] = (),
    ) -> AllocationPlan:
        """Crea un plan sin mutar saldos."""
        available = _decimal(source_amount)
        if available <= 0 or not source_currency:
            raise AllocationError("El efectivo y su moneda deben ser mayores que cero.")
        existing = set(existing_keys)
        lines: list[AllocationLine] = []
        requested: dict[str, Decimal] = {}
        consumed = Decimal("0")
        for request in requests:
            item = self.resolver.resolve(request.document_id)
            if request.idempotency_key and request.idempotency_key in existing:
                continue
            amount = item.outstanding if request.amount is None else _decimal(request.amount)
            if amount <= 0:
                raise AllocationError(f"El importe aplicado a {item.document_id} debe ser mayor que cero.")
            item_key = self.resolver._key(item)
            total = requested.get(item_key, Decimal("0")) + amount
            if total > item.outstanding:
                raise AllocationOverpaymentError(f"La asignación excede el saldo de {item.document_id}.")
            requested[item_key] = total
            rate = self._rate(item.currency, source_currency, request.rate)
            source_line = (amount * rate).quantize(Decimal("0.0001"))
            if consumed + source_line > available:
                raise AllocationOverpaymentError("Las asignaciones exceden el efectivo disponible.")
            consumed += source_line
            lines.append(
                AllocationLine(
                    document_id=item.document_id,
                    document_type=item.document_type,
                    document_currency=item.currency,
                    source_currency=source_currency,
                    document_amount=amount,
                    source_amount=source_line,
                    rate=rate,
                    idempotency_key=request.idempotency_key,
                )
            )
        return AllocationPlan(source_currency=source_currency, source_amount=available, lines=tuple(lines))

    @staticmethod
    def _rate(document_currency: str, source_currency: str, requested_rate: Decimal | None) -> Decimal:
        """Valida la tasa documento→origen."""
        if document_currency == source_currency:
            if requested_rate is not None and _decimal(requested_rate) != 1:
                raise AllocationCurrencyError("La tasa en la misma moneda debe ser 1.")
            return Decimal("1")
        if requested_rate is None or _decimal(requested_rate) <= 0:
            raise AllocationCurrencyError("Se requiere una tasa positiva entre monedas distintas.")
        return _decimal(requested_rate)


class AllocationExecutor:
    """Ejecuta planes con rollback e idempotencia por clave."""

    def __init__(self, resolver: OpenItemResolver) -> None:
        """Inicializa el ejecutor."""
        self.resolver = resolver
        # La memoria de idempotencia vive en el resolver para que dos
        # invocaciones de ``apply_allocation`` compartan la misma operación.
        self._applied = resolver._applied

    def execute(
        self,
        plan: AllocationPlan,
        *,
        persist: Callable[[AllocationLine], Any] | None = None,
        rollback: Callable[[], Any] | None = None,
    ) -> tuple[AllocationLine, ...]:
        """Aplica un plan y revierte el estado si la persistencia falla."""
        state = self.resolver.snapshot()
        applied = dict(self._applied)
        output: list[AllocationLine] = []
        try:
            for line in plan.lines:
                key = line.idempotency_key
                if key and key in self._applied:
                    if self._applied[key] != line:
                        raise AllocationIdempotencyError(f"La clave {key} ya fue usada con otro importe.")
                    output.append(line)
                    continue
                self.resolver.consume(line.document_id, line.document_amount)
                if persist is not None:
                    persist(line)
                if key:
                    self._applied[key] = line
                output.append(line)
        except Exception:
            self.resolver.restore(state)
            self._applied.clear()
            self._applied.update(applied)
            if rollback is not None:
                rollback()
            raise
        return tuple(output)


def plan_allocation(
    source_amount: Decimal,
    source_currency: str,
    requests: Iterable[AllocationRequest],
    *,
    resolver: OpenItemResolver,
    existing_keys: Iterable[str] = (),
) -> AllocationPlan:
    """Planea una asignación mediante la API estable del motor."""
    return AllocationPlanner(resolver).plan(source_amount, source_currency, requests, existing_keys=existing_keys)


def apply_allocation(
    plan: AllocationPlan,
    *,
    resolver: OpenItemResolver,
    persist: Callable[[AllocationLine], Any] | None = None,
    rollback: Callable[[], Any] | None = None,
) -> tuple[AllocationLine, ...]:
    """Aplica una asignación mediante la API estable del motor."""
    return AllocationExecutor(resolver).execute(plan, persist=persist, rollback=rollback)
