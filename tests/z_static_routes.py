from collections import namedtuple

"".encode("utf-8"),

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
            "Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "Información General de la Entidad".encode("utf-8"),
            "Datos Generales:".encode("utf-8"),
            "Identificador: cacao".encode("utf-8"),
            "Razón Social: Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "Nombre: Choco Sonrisas".encode("utf-8"),
            "ID Fiscal: J0310000000000".encode("utf-8"),
            "Tipo: Sociedad".encode("utf-8"),
            "Datos de Contacto:".encode("utf-8"),
            "Página Web: chocoworld.com".encode("utf-8"),
            "Correo Electrónico: info@chocoworld.com".encode("utf-8"),
            "Telefono: +505 8456 6543".encode("utf-8"),
            "Telefono: +505 8456 7543".encode("utf-8"),
            "Fax: +505 8456 7545".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/entity/edit/cacao",
        text=[
            "/accounts/entity/cacao".encode("utf-8"),
            "Editar Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "Informacion Basica:".encode("utf-8"),
            "Nombre Comercial:".encode("utf-8"),
            "Choco Sonrisas".encode("utf-8"),
            "Razon Social:".encode("utf-8"),
            "Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "ID Fiscal:".encode("utf-8"),
            "J0310000000000".encode("utf-8"),
            "Informacion de Contacto:".encode("utf-8"),
            "Correo Electronico:".encode("utf-8"),
            "info@chocoworld.com".encode("utf-8"),
            "Pagina Web:".encode("utf-8"),
            "chocoworld.com".encode("utf-8"),
            "Telefono 1:".encode("utf-8"),
            "+505 8456 6543".encode("utf-8"),
            "Telefono 2:".encode("utf-8"),
            "+505 8456 7543".encode("utf-8"),
            "Fax:".encode("utf-8"),
            "+505 8456 7545".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/accounts",
        text=[
            "Catalogo de Cuentas Contables.".encode("utf-8"),
            "Seleccionar Entidad.".encode("utf-8"),
            "<p><strong>Entidad Actual:</strong> Choco Sonrisas Sociedad Anonima</p>".encode("utf-8"),
            "Actualizar".encode("utf-8"),
            "Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "Mundo Cafe Sociedad Anonima".encode("utf-8"),
            "Mundo Sabor Sociedad Anonima".encode("utf-8"),
            "cacao".encode("utf-8"),
            "cafe".encode("utf-8"),
            "dulce".encode("utf-8"),
            "/accounts/account/11.01.001.002".encode("utf-8"),
            "11.01.001.002 - Fondos por Depositar".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/accounts?entidad=cafe",
        text=[
            "Catalogo de Cuentas Contables.".encode("utf-8"),
            "Mundo Cafe Sociedad Anonima".encode("utf-8"),
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
        ],
    ),
    Route(
        url="/accounts/accounting_period",
        text=[
            "Listado de Períodos Contables.".encode("utf-8"),
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
    Route(
        url="/accounts/series",
        text=[
            "Listado de Series e Indetificadores.".encode("utf-8"),
            "Nueva Serie".encode("utf-8"),
            "Seleccionar Tipo de Documento.".encode("utf-8"),
            "Filtrar por Documento".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/series?doc=journal",
        text=["Listado de Series e Indetificadores.".encode("utf-8"), "Nueva Serie".encode("utf-8")],
    ),
    Route(
        url="/accounts/serie/new",
        text=[
            "Crear Nueva Serie.".encode("utf-8"),
            "Datos de la nueva serie:".encode("utf-8"),
            "Nueva Serie:".encode("utf-8"),
            "Documento:".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/unit/matriz",
        text=[
            "Casa Matriz".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/unit/new",
        text=[
            "Crear Nueva Unidad de Negocios.".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounts/unit/new",
        text=[
            "Crear Nueva Unidad de Negocios.".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/gl/list",
        text=[
            "Listado de Comprobantes Contables.".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/gl/new",
        text=[
            "Crear un Nuevo Comprobante de Diario.".encode("utf-8"),
        ],
    ),
]
