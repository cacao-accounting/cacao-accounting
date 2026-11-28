# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La conversión de cotización valida la fecha antes de compararla.

Escenario de negocio (issue #2125): con ``posting_date`` ausente o inválida,
``_parse_date`` devuelve None y la comparación ``None > valid_until`` lanzaba
TypeError, que la ruta no capturaba (HTTP 500).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from cacao_accounting.ventas.services import validate_sales_quotation_expiry


def _cotizacion(valid_until: date | None) -> SimpleNamespace:
    return SimpleNamespace(valid_until=valid_until)


def test_la_fecha_ausente_se_rechaza_como_validacion():
    """None produce ValueError controlado, no TypeError."""
    with pytest.raises(ValueError, match="fecha de conversión es obligatoria"):
        validate_sales_quotation_expiry(_cotizacion(date(2026, 10, 31)), None)


def test_el_ultimo_dia_de_vigencia_es_inclusivo():
    """Convertir el mismo día permitido no se rechaza."""
    validate_sales_quotation_expiry(_cotizacion(date(2026, 10, 31)), date(2026, 10, 31))


def test_una_fecha_posterior_a_la_vigencia_se_rechaza():
    """El día siguiente ya está fuera de la vigencia."""
    with pytest.raises(ValueError, match="cotización vencida"):
        validate_sales_quotation_expiry(_cotizacion(date(2026, 10, 31)), date(2026, 11, 1))
