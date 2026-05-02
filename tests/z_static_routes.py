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
        url="/ping",
        text=[
        ],
    ),
    Route(
        url="/development",
        text=["Información para desarrolladores.".encode("utf-8")],
    ),
    Route(
        url="/accounting/",
        text=[
            "Módulo de Contabilidad.".encode("utf-8"),
            "Configuración".encode("utf-8"),
            "Entidades".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/entity/list",
        text=[
            "Listado de Entidades.".encode("utf-8"),
            "Nueva Entidad".encode("utf-8"),
            "Código".encode("utf-8"),
            "Razón Social".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/entity/cacao",
        text=[
            "Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "Datos Generales".encode("utf-8"),
            "Identificador".encode("utf-8"),
            "Razón Social".encode("utf-8"),
            "Nombre Comercial".encode("utf-8"),
            "Choco Sonrisas".encode("utf-8"),
            "ID Fiscal".encode("utf-8"),
            "J0310000000000".encode("utf-8"),
            "Tipo".encode("utf-8"),
            "Sociedad".encode("utf-8"),
            "Datos de Contacto".encode("utf-8"),
            "Página Web".encode("utf-8"),
            "chocoworld.com".encode("utf-8"),
            "info@chocoworld.com".encode("utf-8"),
            "+505 8456 6543".encode("utf-8"),
            "+505 8456 7543".encode("utf-8"),
            "+505 8456 7545".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/entity/edit/cacao",
        text=[
            "/accounting/entity/cacao".encode("utf-8"),
            "Editar Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "Información Básica".encode("utf-8"),
            "Nombre Comercial".encode("utf-8"),
            "Choco Sonrisas".encode("utf-8"),
            "Razón Social".encode("utf-8"),
            "Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "ID Fiscal".encode("utf-8"),
            "J0310000000000".encode("utf-8"),
            "Información de Contacto".encode("utf-8"),
            "Correo Electrónico".encode("utf-8"),
            "info@chocoworld.com".encode("utf-8"),
            "Página Web".encode("utf-8"),
            "chocoworld.com".encode("utf-8"),
            "Teléfono 1".encode("utf-8"),
            "+505 8456 6543".encode("utf-8"),
            "Teléfono 2".encode("utf-8"),
            "+505 8456 7543".encode("utf-8"),
            "Fax".encode("utf-8"),
            "+505 8456 7545".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/accounts",
        text=[
            "Catálogo de Cuentas Contables.".encode("utf-8"),
            "Entidad".encode("utf-8"),
            "<strong>Entidad:</strong> Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "Actualizar".encode("utf-8"),
            "Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "Mundo Cafe Sociedad Anonima".encode("utf-8"),
            "Mundo Sabor Sociedad Anonima".encode("utf-8"),
            "cacao".encode("utf-8"),
            "cafe".encode("utf-8"),
            "dulce".encode("utf-8"),
            "/accounting/account/cacao/11.01.001.002".encode("utf-8"),
            "Fondos por Depositar".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/accounts?entidad=cafe",
        text=[
            "Catálogo de Cuentas Contables.".encode("utf-8"),
            "Mundo Cafe Sociedad Anonima".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/accounts?entidad=dulce",
        text=[
            "Catálogo de Cuentas Contables.".encode("utf-8"),
            "Mundo Sabor Sociedad Anonima".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/costs_center",
        text=[
            "Catálogo de Centros de Costos.".encode("utf-8"),
            "Entidad".encode("utf-8"),
            "Entidad:".encode("utf-8"),
            "Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "Actualizar".encode("utf-8"),
            "Mundo Cafe Sociedad Anonima".encode("utf-8"),
            "Mundo Sabor Sociedad Anonima".encode("utf-8"),
            "<strong>Entidad:</strong> Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "Centro Costos Predeterminado".encode("utf-8"),
            "/accounting/costs_center/A00000".encode("utf-8"),
            "Centro Costos Nivel 0".encode("utf-8"),
            "/accounting/costs_center/B00000".encode("utf-8"),
            "B00001 \u2014 Centro Costos Nivel 1".encode("utf-8"),
            "B00011 \u2014 Centro Costos Nivel 2".encode("utf-8"),
            "B00111 \u2014 Centro Costos Nivel 3".encode("utf-8"),
            "B01111 \u2014 Centro Costos Nivel 4".encode("utf-8"),
            "B00011 \u2014 Centro Costos Nivel 2".encode("utf-8"),
            "B11111 \u2014 Centro Costos Nivel 5".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/costs_center?entidad=cacao",
        text=[
            "Catálogo de Centros de Costos.".encode("utf-8"),
            "Entidad".encode("utf-8"),
            "Entidad:".encode("utf-8"),
            "Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "Actualizar".encode("utf-8"),
            "Mundo Cafe Sociedad Anonima".encode("utf-8"),
            "Mundo Sabor Sociedad Anonima".encode("utf-8"),
            "<strong>Entidad:</strong> Choco Sonrisas Sociedad Anonima".encode("utf-8"),
            "Centro Costos Predeterminado".encode("utf-8"),
            "/accounting/costs_center/A00000".encode("utf-8"),
            "Centro Costos Nivel 0".encode("utf-8"),
            "/accounting/costs_center/B00000".encode("utf-8"),
            "B00001 \u2014 Centro Costos Nivel 1".encode("utf-8"),
            "B00011 \u2014 Centro Costos Nivel 2".encode("utf-8"),
            "B00111 \u2014 Centro Costos Nivel 3".encode("utf-8"),
            "B01111 \u2014 Centro Costos Nivel 4".encode("utf-8"),
            "B00011 \u2014 Centro Costos Nivel 2".encode("utf-8"),
            "B11111 \u2014 Centro Costos Nivel 5".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/costs_center?entidad=cafe",
        text=[
            "Catálogo de Centros de Costos.".encode("utf-8"),
            "Entidad".encode("utf-8"),
            "<strong>Entidad:</strong> Mundo Cafe Sociedad Anonima".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/costs_center?entidad=dulce",
        text=[
            "Catálogo de Centros de Costos.".encode("utf-8"),
            "Entidad".encode("utf-8"),
            "<strong>Entidad:</strong> Mundo Sabor Sociedad Anonima".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/unit/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/contabilidad/templates/contabilidad/unidad_lista.html".encode(
                "utf-8"
            ),
            "Listado de Unidades de Negocio.".encode("utf-8"),
            "Código".encode("utf-8"),
            "Nombre".encode("utf-8"),
            "Entidad".encode("utf-8"),
            "/accounting/unit/new".encode("utf-8"),
            "matriz".encode(),
            "masaya".encode(),
            "movil".encode(),
            "Casa Matriz".encode(),
            "Masaya".encode(),
            "/accounting/entity/cacao".encode(),
        ],
    ),
    Route(
        url="/accounting/project/list",
        text=[
            "Listado de Proyectos.".encode("utf-8"),
            "Código".encode("utf-8"),
            "Nombre".encode("utf-8"),
            "Fecha Inicio".encode("utf-8"),
            "Fecha Fin".encode("utf-8"),
            "Proyecto Demostracion".encode(),
            "Proyecto Demo".encode(),
            "Proyecto Prueba".encode(),
            """class="bi bi-circle-fill" style="color:LimeGreen""".encode(),
        ],
    ),
    Route(
        url="/accounting/currency/list",
        text=[
            "Listado de Monedas.".encode("utf-8"),
            "Nueva Moneda".encode("utf-8"),
            "Nombre".encode("utf-8"),
            "Moneda".encode("utf-8"),
            "data-render-currency-ok".encode(),
        ],
    ),
    Route(
        url="/accounting/exchange",
        text=[
            "Listado de Tasas de Cambio.".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/accounting_period",
        text=[
            "Listado de Períodos Contables.".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/account/cacao/1",
        text=[
            "Cuenta Contable".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/costs_center/A00000",
        text=[
            "Centro de Costos.".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/series",
        text=[
            "Listado de Series e Identificadores.".encode("utf-8"),
            "Nueva Serie".encode("utf-8"),
            "Tipo de Documento".encode("utf-8"),
            "Filtrar".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/series?doc=journal",
        text=["Listado de Series e Identificadores.".encode("utf-8"), "Nueva Serie".encode("utf-8")],
    ),
    Route(
        url="/accounting/serie/new",
        text=[
            "Crear Nueva Serie.".encode("utf-8"),
            "Nueva Serie".encode("utf-8"),
            "Documento".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/book/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/contabilidad/templates/contabilidad/book_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/accounting/unit/matriz",
        text=[
            "Casa Matriz".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/unit/new",
        text=[
            "Crear Nueva Unidad de Negocio.".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/unit/new",
        text=[
            "Crear Nueva Unidad de Negocio.".encode("utf-8"),
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
