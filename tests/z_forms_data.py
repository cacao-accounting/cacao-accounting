from collections import namedtuple

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
    Form(
        ruta="/accounts/entity/edit/cacao",
        data={
            "nombre_comercial": "Choco Sonrisas edit",
            "razon_social": "Choco Sonrisas, S.A.",
            "id_fiscal": "J031000000000",
            "correo_electronico": "info2@chocoworld.com",
            "web": "chocoworld.com",
            "telefono1": "+505 0000 0000",
            "telefono2": "+505 1111 1111",
            "fax": "+505 2222 2222",
        },
        file=None,
        flash=None,
    ),
    Form(
        ruta="/accounts/unit/new",
        data={
            "nombre": "Unidad de Prueba",
            "razon_social": "ciatesting, s.a.",
            "entidad": "cacao",
            "id": "E001",
        },
        file=None,
        flash=None,
    ),
]
