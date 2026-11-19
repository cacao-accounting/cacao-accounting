# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2181: una serie vacía no anula la configuración por cuenta y tipo.

El formulario de pago inicializa la serie y el contador como cadena vacía.
El servicio solo consultaba `BankAccountNumberingConfig` cuando recibía
`None`, por lo que ignoraba la configuración guardada.
"""

from __future__ import annotations

from types import SimpleNamespace

from cacao_accounting.bancos import services


def test_empty_form_fields_fall_back_to_the_account_configuration(monkeypatch):
    """La configuración por cuenta/tipo gana frente a defaults generales."""
    monkeypatch.setattr(
        services,
        "_resolve_bank_account_numbering_config",
        lambda *_args: SimpleNamespace(
            naming_series_id="SERIE-CUENTA",
            use_external_counter=True,
            external_counter_id="CHEQUERA-CUENTA",
        ),
    )
    payment = SimpleNamespace(bank_account_id="BANK-1", payment_type="pay")

    series, counter = services._resolve_payment_numbering(
        {"naming_series_id": "", "external_counter_id": ""},
        payment,
        "check",
    )

    assert series == "SERIE-CUENTA"
    assert counter == "CHEQUERA-CUENTA"


def test_explicit_payment_values_keep_priority(monkeypatch):
    """Una selección explícita del usuario no se reemplaza por la configuración."""
    monkeypatch.setattr(
        services,
        "_resolve_bank_account_numbering_config",
        lambda *_args: SimpleNamespace(
            naming_series_id="SERIE-CUENTA",
            use_external_counter=True,
            external_counter_id="CHEQUERA-CUENTA",
        ),
    )
    payment = SimpleNamespace(bank_account_id="BANK-1", payment_type="pay")

    series, counter = services._resolve_payment_numbering(
        {"naming_series_id": "SERIE-ELEGIDA", "external_counter_id": "CHEQUERA-ELEGIDA"},
        payment,
        "check",
    )

    assert series == "SERIE-ELEGIDA"
    assert counter == "CHEQUERA-ELEGIDA"
