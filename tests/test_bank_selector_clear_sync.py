# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2273 y #2280: limpiar un selector derivado sincroniza el estado del formulario."""

from __future__ import annotations

import cacao_accounting
from html import unescape
from pathlib import Path


def _html(cliente, ruta: str) -> str:
    """Devuelve el HTML renderizado de un formulario real de CTM."""
    respuesta = cliente.get(ruta)
    assert respuesta.status_code == 200, ruta
    # El navegador decodifica las entidades HTML antes de ejecutar el Alpine;
    # comparar el texto ya decodificado evita depender del escape de Jinja.
    return unescape(respuesta.get_data(as_text=True))


def test_macro_smart_select_expone_on_clear():
    """La macro compartida permite conectar la limpieza del Smart Select."""
    macro = (Path(cacao_accounting.__file__).parent / "templates" / "transaction_form_macros.html").read_text(encoding="utf-8")
    assert "on_clear=None" in macro
    assert 'onClear: {{ on_clear if on_clear else "null" }},' in macro


def test_gasto_caja_chica_limpia_moneda_y_paso_del_importe(app, entorno_contable, authenticated_client):
    """Quitar el fondo restaura la moneda y el step del importe."""
    del entorno_contable
    html = _html(authenticated_client("admin"), "/cash_management/petty-cash-expense/new")
    assert "document.getElementById('pc_currency'); if (el) el.value = opt.currency" in html
    limpieza = (
        "onClear: function(){ var el = document.getElementById('pc_currency'); "
        "if (el) el.value = ''; var amount = document.getElementById('amount'); "
        "if (amount) amount.step = '0.01'; }"
    )
    assert limpieza in html


def test_vale_caja_chica_limpia_moneda(app, entorno_contable, authenticated_client):
    """El vale comparte el patrón de limpieza de moneda del gasto."""
    del entorno_contable
    html = _html(authenticated_client("admin"), "/cash_management/petty-cash-voucher/new")
    limpieza = "onClear: function(){ var el = document.getElementById('pc_currency'); " "if (el) el.value = ''; }"
    assert limpieza in html


def test_nota_bancaria_limpia_cuenta_y_moneda(app, entorno_contable, authenticated_client):
    """La nota enlaza el ID del header y limpia cuenta y moneda al invalidar."""
    del entorno_contable
    html = _html(authenticated_client("admin"), "/cash_management/payment/debit-note/new")
    assert 'x-effect="header.bank_account_id = selectedValue"' in html
    assert "onClear: function() { header.bank_account_id = ''; header.currency = ''; }" in html
    assert "if (!this.header.company || !this.header.bank_account_id" in html


def test_transferencia_limpia_moneda_y_tipo_de_cambio(app, entorno_contable, authenticated_client):
    """Origen y destino conservan el ID enlazado y limpian su moneda derivada."""
    del entorno_contable
    html = _html(authenticated_client("admin"), "/cash_management/payment/transfer/new")
    assert 'x-effect="header.bank_account_id = selectedValue"' in html
    assert 'x-effect="header.target_bank_account_id = selectedValue"' in html
    assert "onClear: function(){ header.currency = ''; header.exchange_rate = 1; }" in html
    assert "onClear: function(){ header.target_currency = ''; header.exchange_rate = 1; }" in html
    assert "!this.header.bank_account_id || !this.header.target_bank_account_id" in html
