# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2070, #2073, #2074: los mensajes nuevos están en el catálogo inglés."""

from __future__ import annotations

import gettext


def test_validaciones_de_importacion_estan_traducidas():
    """Los errores visibles de las tres validaciones tienen traducción compilada."""
    with open("cacao_accounting/translations/en/LC_MESSAGES/messages.mo", "rb") as archivo:
        traducciones = gettext.GNUTranslations(archivo)

    assert traducciones.gettext("El campo enabled debe ser booleano.") == "The enabled field must be boolean."
    assert (
        traducciones.gettext("El subtipo del documento no coincide con la referencia.")
        == "The document subtype does not match the reference."
    )
    assert (
        traducciones.gettext("El tipo de pago no coincide con el documento de referencia.")
        == "The payment type does not match the reference document."
    )
