# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1029: la apócope del español se aplica solo cuando la cifra precede a una escala."""

from __future__ import annotations

import pytest

from cacao_accounting.num2words import num2words


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (1, "UNO"),
        (21, "VEINTIUNO"),
        (31, "TREINTA Y UNO"),
        (41, "CUARENTA Y UNO"),
        (51, "CINCUENTA Y UNO"),
        (61, "SESENTA Y UNO"),
        (71, "SETENTA Y UNO"),
        (81, "OCHENTA Y UNO"),
        (91, "NOVENTA Y UNO"),
        (101, "CIENTO UNO"),
    ],
)
def test_cifra_aislada_conserva_la_forma_plena(number: int, expected: str) -> None:
    """Sin escala a continuación el importe usa UNO, no la forma apocopada."""
    assert num2words(number, currency="USD", lang="es") == f"{expected} USD CON 00/100"


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (21000, "VEINTIÚN MIL"),
        (31000, "TREINTA Y UN MIL"),
        (41000, "CUARENTA Y UN MIL"),
        (51000, "CINCUENTA Y UN MIL"),
        (61000, "SESENTA Y UN MIL"),
        (71000, "SETENTA Y UN MIL"),
        (81000, "OCHENTA Y UN MIL"),
        (91000, "NOVENTA Y UN MIL"),
        (101000, "CIENTO UN MIL"),
        (121000, "CIENTO VEINTIÚN MIL"),
    ],
)
def test_multiplicador_de_mil_aplica_la_apocope(number: int, expected: str) -> None:
    """Ante la escala mil la cifra terminal en uno se apocopa de forma uniforme."""
    assert num2words(number, currency="USD", lang="es") == f"{expected} USD CON 00/100"


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (21000000, "VEINTIÚN MILLONES"),
        (31000000, "TREINTA Y UN MILLONES"),
        (91000000, "NOVENTA Y UN MILLONES"),
        (1000001, "UN MILLÓN UNO"),
    ],
)
def test_multiplicador_de_millon_aplica_la_apocope(number: int, expected: str) -> None:
    """La misma regla rige para millones y para el resto que sigue a la escala."""
    assert num2words(number, currency="USD", lang="es") == f"{expected} USD CON 00/100"


def test_importe_con_centavos_conserva_ambas_formas() -> None:
    """El importe completo combina la apócope del multiplicador y la unidad final."""
    assert num2words(31000.5, currency="USD", lang="es") == "TREINTA Y UN MIL USD CON 50/100"
    assert num2words(-31.5, currency="NIO", lang="es") == "MENOS TREINTA Y UNO NIO CON 50/100"


def test_ingles_no_resulta_afectado() -> None:
    """La regla es propia del español y no altera la composición en inglés."""
    assert num2words(31000, currency="USD", lang="en") == "THIRTY ONE THOUSAND USD AND 00/100"
