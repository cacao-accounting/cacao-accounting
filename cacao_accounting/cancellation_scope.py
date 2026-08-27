# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Predicados de alcance de anulación para consultas contables.

Centraliza los tres alcances que exige la Sección 5 del issue de períodos:

- **Vista ordinaria** (``ordinary_scope``): excluye el par original anulado y su
  contrapartida técnica. Es el alcance de los reportes que un usuario contable o
  auditor ve en el día a día.
- **Vista de auditoría** (``audit_scope``): incluye ambos lados y su metadata
  para reconstruir la anulación completa; no usa ninguna exclusión.
- **Cálculo append-only** (``append_only_scope``): suma los movimientos del
  período sin borrar historia mediante flags. Como el par se anula dentro del
  mismo período, excluirlo o incluirlo da el mismo saldo; se expresa de forma
  explícita para no mezclar este alcance con el de las vistas.
"""

from __future__ import annotations

from typing import Any


def ordinary_gl_scope() -> tuple[Any, Any]:
    """Restricciones GL para la vista ordinaria: excluye originales anulados y contrapartidas."""
    from cacao_accounting.database import GLEntry

    return (GLEntry.is_cancelled.is_(False), GLEntry.is_reversal.is_(False))


def audit_gl_scope() -> tuple[Any, ...]:
    """Sin restricción de anulación: la vista de auditoría incluye ambos lados."""
    return ()


def cancelled_originals_scope() -> tuple[Any]:
    """Muestra solo los originales anulados (no las contrapartidas técnicas)."""
    from cacao_accounting.database import GLEntry

    return (GLEntry.is_cancelled.is_(True),)


def append_only_gl_scope() -> tuple[Any, Any]:
    """Movimientos que alimentan el cálculo del período (append-only).

    El original anulado y su reverso pertenecen al mismo período y se anulan
    entre sí, por lo que ambos se excluyen del resultado del período sin alterar
    el saldo y sin romper la historia.
    """
    return ordinary_gl_scope()
