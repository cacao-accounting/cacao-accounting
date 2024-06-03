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
]
