# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2055: los enlaces de impresión envían siempre la compañía del documento."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "cacao_accounting"


def test_toda_llamada_de_impresion_declara_compania():
    """Sin company el fallback del usuario puede autorizar otra compañía."""
    llamadas: list[tuple[Path, str]] = []
    for plantilla in RAIZ.rglob("*.html"):
        texto = plantilla.read_text(encoding="utf-8")
        for linea in texto.splitlines():
            if "document_print_button(" in linea and "macro " not in linea:
                llamadas.append((plantilla, linea.strip()))

    assert llamadas
    sin_compannia = [(ruta, linea) for ruta, linea in llamadas if "company=" not in linea]
    assert not sin_compannia, f"llamadas sin company: {sin_compannia}"
