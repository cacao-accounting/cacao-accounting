# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1283: helpers retirados de terceros no vuelven sin un consumidor."""

from importlib import import_module

import pytest


@pytest.mark.parametrize("symbol", ["party_account_labels", "build_party_code"])
def test_party_management_keeps_retired_helpers_absent(symbol):
    """The party-management module retains only the called code-generation entry point."""
    module = import_module("cacao_accounting.party_management")

    assert not hasattr(module, symbol)
    assert callable(module.generate_party_code)
