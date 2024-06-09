from collections import namedtuple

Route = namedtuple(
    "Route",
    ["url", "text"],
)

static_rutes = [
    Route(
        url="/app",
        text=[
            "Cacao Accounting".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts",
        text=[
            "Módulo de Contabilidad.".encode("utf-8"),
            "Configuración".encode("utf-8"),
            "Entidades".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/entity/list",
        text=[
            "Listado de Entidades.".encode("utf-8"),
            "Nueva Entidad".encode("utf-8"),
            "Código de Entidad".encode("utf-8"),
            "Razón Social".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/entity/cacao",
        text=[
            "Identificador: cacao".encode("utf-8"),
            "Página Web: chocoworld.com".encode("utf-8"),
            "Correo Electrónico: info@chocoworld.com".encode("utf-8"),
            "Razón Social: Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "Nombre: Choco Sonrisas".encode("utf-8"),
            "ID Fiscal: J0310000000000".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/unit/list",
        text=[
            "Listado de Unidades de Negocio.".encode("utf-8"),
            "Código de Entidad".encode("utf-8"),
            "Nombre".encode("utf-8"),
            "Entidad".encode("utf-8"),
            "Nueva Unidad de Negocios".encode("utf-8"),
        ],
    ),
]
