# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Canonicalize email addresses used as system-user identities."""


def normalize_user_email(email: str | None) -> str | None:
    """Trim and lowercase an optional email address before storing or comparing it."""
    if email is None:
        return None
    normalized = email.strip().lower()
    return normalized or None
