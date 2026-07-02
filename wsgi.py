# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Ejecuta el servidor WSGI predeterminado."""

from cacao_accounting.config import TESTING_MODE
from cacao_accounting.server import app, server

if __name__ == "__main__":
    if TESTING_MODE:
        app.run(debug=True, port=8080)
    else:
        server()
