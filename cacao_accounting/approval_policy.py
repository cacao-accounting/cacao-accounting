# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Shared Cloud approval authority and independent-preparer policy."""

from typing import Any

from sqlalchemy import select

from cacao_accounting.database import Entity, Modules, Roles, RolesAccess, RolesUser, User, UserCompanyAccess, database
from cacao_accounting.document_flow.registry import get_document_type


def is_admin(user: Any) -> bool:
    """Recognize classification and active administrative role assignments."""
    if getattr(user, "classification", None) == "admin":
        return True
    return (
        database.session.execute(
            select(RolesUser.id)
            .join(Roles, Roles.id == RolesUser.role_id)
            .where(RolesUser.user_id == getattr(user, "id", None), RolesUser.active.is_(True), Roles.name == "admin")
        ).first()
        is not None
    )


def module_access(user: Any, module_name: str) -> list[Any]:
    """Load permissions from active roles for an enabled module."""
    return list(
        database.session.execute(
            select(RolesAccess)
            .join(Modules, Modules.id == RolesAccess.module_id)
            .join(RolesUser, RolesUser.role_id == RolesAccess.rol_id)
            .where(
                RolesUser.user_id == getattr(user, "id", None),
                RolesUser.active.is_(True),
                Modules.module == module_name,
                Modules.enabled.is_(True),
            )
        ).scalars()
    )


def module_rank(user: Any, module_name: str) -> int | None:
    """Return the highest explicitly classified active rank without granting permissions."""
    if is_admin(user):
        return 4
    ranks = [row.approval_rank for row in module_access(user, module_name) if row.approval_rank in {1, 2, 3}]
    return max(ranks) if ranks else None


def authorized(user: Any, company: str, module_name: str, action: str = "approve") -> bool:
    """Check active identity, enabled company, module permissions and tenant scope."""
    if getattr(user, "active", None) is not True:
        return False
    entity = database.session.execute(select(Entity).where(Entity.code == company, Entity.enabled.is_(True))).first()
    module_enabled = database.session.execute(
        select(Modules.id).where(Modules.module == module_name, Modules.enabled.is_(True))
    ).first()
    if not entity or not module_enabled:
        return False
    if is_admin(user):
        return True
    scoped = database.session.execute(
        select(UserCompanyAccess.id).where(UserCompanyAccess.user_id == user.id, UserCompanyAccess.company_code == company)
    ).first()
    permissions = module_access(user, module_name)
    return bool(scoped and any(row.access for row in permissions) and any(getattr(row, action, False) for row in permissions))


def document_module(doctype: str) -> str:
    """Resolve authority from the existing document registry."""
    if doctype == "import_landed_cost":
        return "purchases"
    spec = get_document_type(doctype)
    return str(spec.permission_module or spec.module)


def build_policy(document: Any, requester_id: str, doctype: str) -> dict[str, Any]:
    """Freeze preparer provenance and ranks before an independent review starts."""
    module = document_module(doctype)
    creator_id = getattr(document, "created_by", None) or getattr(document, "user_id", None)
    if not creator_id:
        raise ValueError("missing_preparer")
    ids = {str(value) for value in (creator_id, getattr(document, "modified_by", None), requester_id) if value}
    preparers = []
    for user_id in sorted(ids):
        user = database.session.get(User, user_id)
        rank = module_rank(user, module) if user else None
        if rank is None:
            raise ValueError("unclassified_preparer")
        preparers.append({"user_id": user_id, "rank": rank})
    return {"requires_independent": True, "module": module, "preparers": preparers}


def permits_independent_approval(snapshot: dict[str, Any], user: Any, company: str) -> bool:
    """Enforce strict independence and seniority under the frozen review snapshot.

    The review must be performed by a different, active approver whose explicit
    approval rank is at least as high as the highest preparer rank. This keeps
    four-eyes review auditable and prevents an implicit manager override of an
    admin-prepared document.
    """
    module = snapshot.get("module", "")
    if not authorized(user, company, module):
        return False
    preparers = snapshot.get("preparers", [])
    if not preparers or any(str(item["user_id"]) == str(user.id) for item in preparers):
        return False
    rank = module_rank(user, module)
    if rank is None:
        return False
    preparer_ranks = [item["rank"] for item in preparers if item.get("rank") in {1, 2, 3, 4}]
    if not preparer_ranks:
        return False
    return rank >= max(preparer_ranks)
