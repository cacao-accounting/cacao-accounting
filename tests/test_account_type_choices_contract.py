# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1914: todo tipo de cuenta usado por el motor existe en el formulario."""

from __future__ import annotations

from werkzeug.datastructures import MultiDict

from cacao_accounting.contabilidad.forms import FormularioCuenta
from cacao_accounting.contabilidad.forms import ACCOUNT_TYPE_CHOICES


def test_variance_de_liquidacion_de_compra_se_puede_editar(app):
    """El tipo reportado está en choices y pasa el campo real de edición."""
    elegibles = {valor for valor, _etiqueta in ACCOUNT_TYPE_CHOICES}
    assert "purchase_settlement_variance" in elegibles

    with app.test_request_context("/accounting/account/new", method="POST"):
        formulario = FormularioCuenta(
            formdata=MultiDict({"account_type": "purchase_settlement_variance"}),
            meta={"csrf": False},
        )
        assert formulario.account_type.validate(formulario)
