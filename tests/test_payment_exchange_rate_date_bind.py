# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1323: la tasa del pago se consulta con una fecha normalizada.

El formulario envía ``posting_date`` como texto; el bind DATE de SQLite
solo acepta objetos ``date``.
"""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.bancos.services import _resolve_payment_exchange_rate
from cacao_accounting.contabilidad.posting_service import PostingError, _lookup_exchange_rate


def test_lookup_acepta_fecha_texto_del_formulario(entorno_contable_aislado):
    """Una fecha ISO se convierte antes del bind y resuelve la tasa."""
    app = entorno_contable_aislado.app
    with app.app_context():
        assert _lookup_exchange_rate("USD", "NIO", "2026-05-15") == Decimal("36.50")


def test_lookup_conserva_fecha_date(entorno_contable_aislado):
    """El contrato con objetos date no cambia."""
    app = entorno_contable_aislado.app
    with app.app_context():
        assert _lookup_exchange_rate("USD", "NIO", date(2026, 5, 15)) == Decimal("36.50")


def test_pago_multimoneda_resuelve_tasa_con_fecha_texto(entorno_contable_aislado):
    """La resolución del pago usa la fecha del payload sin fallar en SQLite."""
    app = entorno_contable_aislado.app
    with app.app_context():
        rate = _resolve_payment_exchange_rate({"posting_date": "2026-05-15"}, "USD", "cacao")

        assert rate == Decimal("36.50")


def test_fecha_invalida_es_error_controlado(entorno_contable_aislado):
    """Una fecha imposible falla con PostingError, no con TypeError del driver."""
    app = entorno_contable_aislado.app
    with app.app_context():
        with pytest.raises(PostingError, match="inválida"):
            _lookup_exchange_rate("USD", "NIO", "no-es-fecha")
