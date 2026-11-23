# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2249: el identificador de la cola de correos no puede inyectar líneas de registro."""

from __future__ import annotations

import logging

import pytest

from cacao_accounting.messaging.email import EmailError, deliver_email_queue_item


@pytest.mark.parametrize(
    "queue_id",
    [
        "01J0000000000000000000000\nFORGED admin=true",
        "01J0000000000000000000000\r\nFORGED",
        "01J0000000000000000000000\x00",
        "../../etc/passwd",
        "",
        "A" * 65,
    ],
)
def test_rechaza_identificadores_fuera_del_formato(queue_id: str, caplog: pytest.LogCaptureFixture) -> None:
    """Un identificador no ULID se rechaza antes de consultar o registrar nada."""
    with caplog.at_level(logging.DEBUG, logger="cacao_accounting.messaging.email"):
        with pytest.raises(EmailError, match="identificador"):
            deliver_email_queue_item(queue_id, retry=False)

    assert "FORGED" not in caplog.text
    assert "\n" not in caplog.text
