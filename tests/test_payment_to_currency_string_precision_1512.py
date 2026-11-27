# SPDX-License-Identifier: Apache-2.0
"""#1512: serializacion de montos en pago no pierde precision decimal."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def test_payment_to_currency_string_preserves_decimal_precision():
    html = Path("cacao_accounting/bancos/templates/bancos/pago_nuevo.html").read_text(encoding="utf-8")
    match = re.search(r"toCurrencyString:\s*function \(value\) \{.*?\n\s*\},", html, re.DOTALL)
    assert match, "toCurrencyString not found"
    fn = "const toCurrencyString = " + match.group(0).replace("toCurrencyString:", "").rstrip(",")

    node_script = (
        fn
        + "; console.log(toCurrencyString('9999999999999.9999'));"
        + " console.log(toCurrencyString('123456789012.3456'));"
        + " console.log(toCurrencyString('0012.3400'));"
        + " console.log(toCurrencyString('-0.0000'));"
    )
    result = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True)
    lines = result.stdout.strip().splitlines()
    assert lines == ["9999999999999.9999", "123456789012.3456", "12.34", "0"]
