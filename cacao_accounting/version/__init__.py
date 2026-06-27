# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Definición unica de la version de la aplicación."""

# Only update the version if all tests are passing.
# PyPi will refuse to push two packages with the same version
# Keep the version bump in a single commit without other changes included in it to ensure a clean release.

APPNAME = "Cacao Accounting"
APPAUTHOR = "William Moreno Reyes"
MAYOR = "0"
MENOR = "0"
PATCH = "1"
DATE = "20250515"
PRERELEASE = "dev" + DATE
# POSTRELESE = "post" + DATE
POSTRELESE = None

if PRERELEASE:  # pragma: no cover
    VERSION = MAYOR + "." + MENOR + "." + PATCH + "." + PRERELEASE
else:
    if POSTRELESE:
        VERSION = MAYOR + "." + MENOR + "." + PATCH + "." + POSTRELESE
    else:
        VERSION = MAYOR + "." + MENOR + "." + PATCH
