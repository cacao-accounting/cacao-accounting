# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Preflight guards for workflows without an approval submission route."""

from cacao_accounting.i18n import _
from cacao_accounting.runtime_mode import is_desktop_mode


class ApprovalWorkflowRequired(ValueError):
    """Raised when a direct workflow cannot satisfy independent approval."""


def ensure_approval_flow_supported(company: str) -> None:
    """Reject direct posting when Cloud requires approval this flow cannot submit."""
    if is_desktop_mode():
        return

    from cacao_accounting.approval_engine import ApprovalEngine

    if not ApprovalEngine.is_enabled(company) or not ApprovalEngine.requires_different_approver(company):
        return

    raise ApprovalWorkflowRequired(_("Este flujo aún no admite aprobación independiente; no se creó el asiento contable."))
