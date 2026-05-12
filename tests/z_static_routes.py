# ruff: noqa: E501
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
        text=[],
    ),
    Route(
        url="/development",
        text=["Información para desarrolladores.".encode("utf-8")],
    ),
    Route(
        url="/accounting/",
        text=[
            "Módulo de Contabilidad.".encode("utf-8"),
            "La Plantilla fue renderizada correctamente: cacao_accounting/contabilidad/templates/contabilidad.html".encode(
                "utf-8"
            ),
            "Configuración del Módulo".encode("utf-8"),
            "Registros del Módulo".encode("utf-8"),
            "Reportes del Módulo".encode("utf-8"),
            "Entidades".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/entity/list",
        text=[
            "Listado de Entidades".encode("utf-8"),
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
            "Editar Entidad".encode("utf-8"),
            "Choco Sonrisas Sociedad Anonima".encode("utf-8"),
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
            "Listado de Unidades de Negocio".encode("utf-8"),
            "Código".encode("utf-8"),
            "Nombre".encode("utf-8"),
            "Entidad".encode("utf-8"),
            "/accounting/unit/new".encode("utf-8"),
            "matriz".encode(),
            "masaya".encode(),
            "movil".encode(),
            "Casa Matriz".encode(),
            "Masaya".encode(),
        ],
    ),
    Route(
        url="/accounting/project/list",
        text=[
            "Listado de Proyectos".encode("utf-8"),
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
            "Listado de Monedas".encode("utf-8"),
            "Nueva Moneda".encode("utf-8"),
            "Nombre".encode("utf-8"),
            "Moneda".encode("utf-8"),
            "data-render-currency-ok".encode(),
        ],
    ),
    Route(
        url="/accounting/exchange",
        text=[
            "Listado de Tasas de Cambio".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/accounting_period",
        text=[
            "Listado de Períodos Contables".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/account/cacao/1",
        text=[
            "1 - Activos".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/costs_center/A00000",
        text=[
            "A00000 - Centro Costos Predeterminado".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/book/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/contabilidad/templates/contabilidad/book_lista.html".encode(
                "utf-8"
            ),
            "Listado de Libros de Contabilidad".encode("utf-8"),
        ],
    ),
    Route(
        url="/settings/modules",
        text=[
            "Administración de Módulos".encode("utf-8"),
            "Nombre".encode("utf-8"),
            "Activo".encode("utf-8"),
        ],
    ),
    Route(
        url="/settings/users",
        text=[
            "Administración de Usuarios".encode("utf-8"),
            "Usuario".encode("utf-8"),
            "Correo".encode("utf-8"),
        ],
    ),
    Route(
        url="/settings/users/new",
        text=[
            "Crear Usuario".encode("utf-8"),
            "Nombre".encode("utf-8"),
            "Contraseña".encode("utf-8"),
        ],
    ),
    Route(
        url="/auth/profile",
        text=[
            "Mi Perfil".encode("utf-8"),
            "Información personal".encode("utf-8"),
            "Cambiar contraseña".encode("utf-8"),
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
            "Nueva Unidad de Negocio".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/journal/list",
        text=[
            "Listado de Comprobantes Contables.".encode("utf-8"),
            "Nuevo".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/journal/new",
        text=[
            "Comprobante contable".encode("utf-8"),
            "Guardar borrador".encode("utf-8"),
        ],
    ),
    Route(
        url="/cash_management/",
        text=[
            "Módulo de Caja y Bancos".encode("utf-8"),
            "La Plantilla fue renderizada correctamente: cacao_accounting/bancos/templates/bancos.html".encode("utf-8"),
            "Configuración del Módulo".encode("utf-8"),
            "Registros del Módulo".encode("utf-8"),
            "Reportes del Módulo".encode("utf-8"),
        ],
    ),
    Route(
        url="/cash_management/bank/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/bancos/templates/bancos/banco_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/cash_management/bank-account/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/bancos/templates/bancos/banco_cuenta_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/cash_management/payment/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/bancos/templates/bancos/pago_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/cash_management/bank-transaction/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/bancos/templates/bancos/transaccion_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/buying/",
        text=[
            "Módulo de Compras".encode("utf-8"),
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras.html".encode("utf-8"),
            "Configuración del Módulo".encode("utf-8"),
            "Registros del Módulo".encode("utf-8"),
            "Reportes del Módulo".encode("utf-8"),
        ],
    ),
    Route(
        url="/buying/purchase-order/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras/orden_compra_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/buying/purchase-receipt/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras/recepcion_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/buying/purchase-invoice/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras/factura_compra_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/buying/supplier/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras/proveedor_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/inventory/",
        text=[
            "Módulo de Control de Inventario".encode("utf-8"),
            "La Plantilla fue renderizada correctamente: cacao_accounting/inventario/templates/inventario.html".encode(
                "utf-8"
            ),
            "Configuración del Módulo".encode("utf-8"),
            "Registros del Módulo".encode("utf-8"),
            "Reportes del Módulo".encode("utf-8"),
        ],
    ),
    Route(
        url="/inventory/item/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/inventario/templates/inventario/articulo_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/inventory/uom/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/inventario/templates/inventario/uom_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/inventory/warehouse/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/inventario/templates/inventario/bodega_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/inventory/stock-entry/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/inventario/templates/inventario/entrada_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/sales/",
        text=[
            "Módulo de Ventas".encode("utf-8"),
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas.html".encode("utf-8"),
            "Configuración del Módulo".encode("utf-8"),
            "Registros del Módulo".encode("utf-8"),
            "Reportes del Módulo".encode("utf-8"),
        ],
    ),
    Route(
        url="/sales/sales-order/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas/orden_venta_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/sales/delivery-note/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas/entrega_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/sales/sales-invoice/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas/factura_venta_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/sales/customer/list",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas/cliente_lista.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/buying/supplier/new",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras/proveedor_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/buying/purchase-order/new",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras/orden_compra_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/buying/purchase-receipt/new",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras/recepcion_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/buying/purchase-invoice/new",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras/factura_compra_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/sales/customer/new",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas/cliente_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/sales/sales-order/new",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas/orden_venta_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/sales/delivery-note/new",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas/entrega_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/sales/sales-invoice/new",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas/factura_venta_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/inventory/item/new",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/inventario/templates/inventario/articulo_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/inventory/item/ART-001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/inventario/templates/inventario/articulo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/inventory/uom/new",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/inventario/templates/inventario/uom_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/inventory/uom/UND",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/inventario/templates/inventario/uom.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/inventory/warehouse/new",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/inventario/templates/inventario/bodega_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/inventory/warehouse/PRINCIPAL",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/inventario/templates/inventario/bodega.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/inventory/stock-entry/new",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/inventario/templates/inventario/entrada_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/cash_management/bank/new",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/bancos/templates/bancos/banco_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/cash_management/bank-account/new",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/bancos/templates/bancos/banco_cuenta_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/cash_management/payment/new",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/bancos/templates/bancos/pago_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/buying/purchase-order/POR-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras/orden_compra.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/buying/purchase-receipt/REC-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras/recepcion.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/sales/sales-order/SOV-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas/orden_venta.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/sales/delivery-note/ENT-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas/entrega.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/buying/purchase-receipt/new?from_order=POR-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras/recepcion_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/buying/purchase-invoice/new?from_order=POR-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras/factura_compra_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/sales/delivery-note/new?from_order=SOV-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas/entrega_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/sales/sales-invoice/new?from_order=SOV-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas/factura_venta_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/api/buying/purchase-order/POR-DEMO-0000001/items",
        text=[],
    ),
    Route(
        url="/api/sales/sales-order/SOV-DEMO-0000001/items",
        text=[],
    ),
    # ── Detail pages for submitted invoices ───────────────────────────────
    Route(
        url="/buying/purchase-invoice/FCC-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras/factura_compra.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/sales/sales-invoice/FCV-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas/factura_venta.html".encode(
                "utf-8"
            ),
        ],
    ),
    # ── "Crear → Nota de Crédito" shortcuts ───────────────────────────────
    Route(
        url="/buying/purchase-invoice/new?from_return=FCC-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras/factura_compra_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/sales/sales-invoice/new?from_return=FCV-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas/factura_venta_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    # ── "Crear → Pago" shortcuts ──────────────────────────────────────────
    Route(
        url="/cash_management/payment/new?from_purchase_invoice=FCC-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/bancos/templates/bancos/pago_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/cash_management/payment/new?from_sales_invoice=FCV-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/bancos/templates/bancos/pago_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    # ── Item API endpoints for invoices ───────────────────────────────────
    Route(
        url="/api/buying/purchase-invoice/FCC-DEMO-0000001/items",
        text=[],
    ),
    Route(
        url="/api/sales/sales-invoice/FCV-DEMO-0000001/items",
        text=[],
    ),
    # ── Nota de entrega con auto-completar desde recepción aprobada ───────
    Route(
        url="/buying/purchase-invoice/new?from_receipt=REC-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/compras/templates/compras/factura_compra_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    Route(
        url="/sales/sales-invoice/new?from_note=ENT-DEMO-0000001",
        text=[
            "La Plantilla fue renderizada correctamente: cacao_accounting/ventas/templates/ventas/factura_venta_nuevo.html".encode(
                "utf-8"
            ),
        ],
    ),
    # ── Series de Numeracion (NamingSeries) ───────────────────────────────
    Route(
        url="/accounting/naming-series/list",
        text=[
            "La Plantilla fue renderizada correctamente: contabilidad/naming_series_lista.html".encode("utf-8"),
            "Series de Numeracion".encode("utf-8"),
            "Nueva Serie".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/naming-series/new",
        text=[
            "Nueva Serie de Numeracion".encode("utf-8"),
            "Tipo de Documento".encode("utf-8"),
            "Plantilla de Prefijo".encode("utf-8"),
        ],
    ),
    # ── Contadores Externos (ExternalCounter) ─────────────────────────────
    Route(
        url="/accounting/external-counter/list",
        text=[
            "La Plantilla fue renderizada correctamente: contabilidad/external_counter_lista.html".encode("utf-8"),
            "Contadores Externos".encode("utf-8"),
            "Nuevo Contador".encode("utf-8"),
        ],
    ),
    Route(
        url="/accounting/external-counter/new",
        text=[
            "Nuevo Contador Externo".encode("utf-8"),
            "Compania".encode("utf-8"),
        ],
    ),
]
