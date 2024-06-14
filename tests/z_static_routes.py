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
        url="/development",
        text=["Información para desarrolladores.".encode("utf-8")],
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
            "Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "Nombre: Choco Sonrisas".encode("utf-8"),
            "ID Fiscal: J0310000000000".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/entity/edit/cacao",
        text=[
            "Nombre Comercial:".encode("utf-8"),
            "Choco Sonrisas".encode("utf-8"),
            "Razon Social:".encode("utf-8"),
            "Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "ID Fiscal:".encode("utf-8"),
            "J0310000000000".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/accounts",
        text=[
            "Catalogo de Cuentas Contables.".encode("utf-8"),
            "Seleccionar Entidad.".encode("utf-8"),
            "Entidad Actual:".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/accounts?entidad=cafe",
        text=[
            "Catalogo de Cuentas Contables.".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/costs_center",
        text=[
            "Catalogo de Centros de Costos.".encode("utf-8"),
            "Seleccionar Entidad.".encode("utf-8"),
            "Entidad Actual:".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/costs_center?entidad=cafe",
        text=[
            "Catalogo de Centros de Costos.".encode("utf-8"),
            "Seleccionar Entidad.".encode("utf-8"),
            "Entidad Actual:".encode("utf-8"),
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
    Route(
        url="/accounts/project/list",
        text=[
            "Listado de Proyectos.".encode("utf-8"),
            "Código de Proyecto".encode("utf-8"),
            "Nombre".encode("utf-8"),
            "Fecha Inicio".encode("utf-8"),
            "Fecha Fin".encode("utf-8"),
        ],
    ),
    Route(
        url="/currency/list",
        text=[
            "Listado de Monedas.".encode("utf-8"),
            "Nueva Moneda".encode("utf-8"),
            "Nombre".encode("utf-8"),
            "Moneda".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/exchange",
        text=[
            "Listado de Tasas de Cambio.".encode("utf-8"),
            "Nueva Tasa de Cambio".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/accounting_period",
        text=[
            "Listado de Períodos Contables.".encode("utf-8"),
            "Nuevo Período Contable".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/accounting_period",
        text=[
            "Listado de Períodos Contables.".encode("utf-8"),
            "Nuevo Período Contable".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/accounting_period",
        text=[
            "Listado de Períodos Contables.".encode("utf-8"),
            "Nuevo Período Contable".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/account/1",
        text=[
            "Cuenta Contable".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/costs_center/A00000",
        text=[
            "Centro de Costos.".encode("utf-8"),
        ],
    ),
    Route(
        url="/settings",
        text=["Administraión del Sistema.".encode("utf-8"), "Modulos".encode("utf-8")],
    ),
]
