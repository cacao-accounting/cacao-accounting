# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Definición unica de la version de la aplicación."""

# Only update the version if all tests are passing.
# PyPi will refuse to push two packages with the same version
# Keep the version bump in a single commit without other changes included in it to ensure a clean release.

APPNAME = "Cacao Accounting"
APPAUTHOR = "William Moreno Reyes"
MAYOR = "0"
MENOR = "1"
PATCH = "0"
DATE = "20260831"
PRERELEASE = "a1"
POSTRELESE = None


def build_version(
    mayor: str,
    menor: str,
    patch: str,
    prerelease: str | None = None,
    postrelease: str | None = None,
) -> str:
    """Build the package version string from its release components."""
    version = mayor + "." + menor + "." + patch
    if prerelease:
        if prerelease.startswith(("dev", "post", ".")):
            return version + "." + prerelease
        return version + prerelease
    if postrelease:
        if postrelease.startswith((".", "post")):
            return version + "." + postrelease
        return version + ".post" + postrelease
    return version


VERSION = build_version(MAYOR, MENOR, PATCH, PRERELEASE, POSTRELESE)
