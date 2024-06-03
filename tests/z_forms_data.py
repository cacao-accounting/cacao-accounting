from collections import namedtuple
from io import BytesIO

Form = namedtuple("form", ["ruta", "data", "file", "flash"])

forms = [
    Form(
        ruta="/accounts/entity/new",
        data={
            "nombre_comercial": "Compañia de Pruebas",
            "razon_social": "ciatesting, s.a.",
            "id_fiscal": "J08100000000",
            "id": "J081",
        },
        file=None,
        flash=None,
    ),
]
