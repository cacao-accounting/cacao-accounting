# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1985: el responsable rechazado no inyecta código en el x-data de Alpine.

La ruta re-renderiza el formulario con el valor enviado; ese valor debe viajar
serializado como JSON y escapado para HTML, de modo que un cierre de cadena no
se convierta en una expresión ejecutable.
"""

from __future__ import annotations

PAYLOAD = 'x"; alert(1); //'


def test_responsable_invalido_se_serializa_sin_romper_alpine(app, authenticated_client, entorno_contable):
    """El POST inválido conserva el texto pero no permite salir del literal."""
    del entorno_contable
    response = authenticated_client("admin").post(
        "/cash_management/petty-cash/new",
        data={
            "company": "cacao",
            "name": "Caja con payload",
            "currency": "NIO",
            "account_id": "",
            "custodian_id": PAYLOAD,
            "float_amount": "10",
            "is_active": "on",
        },
    )

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "initialValue: &#34;x\\&#34;; alert(1); //&#34;" in cuerpo
    assert '"x"; alert(1)' not in cuerpo
    assert 'initialValue: "x";' not in cuerpo
