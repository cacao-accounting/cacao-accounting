# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Data para el desarrollo."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from datetime import date, datetime

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.auth import proteger_passwd as _pg
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Bank,
    CostCenter,
    DeliveryNote,
    DeliveryNoteItem,
    Entity,
    ExchangeRate,
    Item,
    Party,
    Project,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    SalesInvoice,
    SalesInvoiceItem,
    SalesOrder,
    SalesOrderItem,
    UOM,
    Unit,
    Warehouse,
)

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------


BASE_USUARIOS = [
    {"user": "admin", "e_mail": "a@dm.com", "password": _pg("admin"), "active": True, "classification": "system"},
    {"user": "audit", "e_mail": "au@dm.com", "password": _pg("audit"), "active": True, "classification": "system"},
    {"user": "analist", "e_mail": "an@dm.com", "password": _pg("analist"), "active": True, "classification": "system"},
    {"user": "conta", "e_mail": "con@dm.com", "password": _pg("conta"), "active": True, "classification": "system"},
    {"user": "contaj", "e_mail": "conj@dm.com", "password": _pg("contaj"), "active": True, "classification": "system"},
    {"user": "compras", "e_mail": "compras@dm.com", "password": _pg("compras"), "active": True, "classification": "system"},
    {
        "user": "comprasj",
        "e_mail": "comprasj@dm.com",
        "password": _pg("comprasj"),
        "active": True,
        "classification": "system",
    },
    {"user": "ventas", "e_mail": "ventas@dm.com", "password": _pg("ventas"), "active": True, "classification": "system"},
    {"user": "ventasj", "e_mail": "ventasj@dm.com", "password": _pg("ventasj"), "active": True, "classification": "system"},
    {"user": "inventario", "e_mail": "in@dm.com", "password": _pg("inventario"), "active": True, "classification": "system"},
    {
        "user": "inventarioj",
        "e_mail": "inj@dm.com",
        "password": _pg("inventarioj"),
        "active": True,
        "classification": "system",
    },
    {"user": "tesoreria", "e_mail": "t@dm.com", "password": _pg("tesoreria"), "active": True, "classification": "system"},
    {"user": "tesoreriaj", "e_mail": "tj@dm.com", "password": _pg("tesoreriaj"), "active": True, "classification": "system"},
    {"user": "pasante", "e_mail": "p@dm.com", "password": _pg("pasante"), "active": True, "classification": "system"},
    {"user": "usuario", "e_mail": "u@dm.com", "password": _pg("usuario"), "active": True, "classification": "system"},
]

USUARIO_ROLES = [
    ("admin", "admin"),
    ("audit", "comptroller"),
    ("analist", "business_analyst"),
    ("conta", "accounting_manager"),
    ("contaj", "accounting_auxiliar"),
    ("compras", "purchasing_manager"),
    ("comprasj", "purchasing_auxiliar"),
    ("ventas", "sales_manager"),
    ("ventasj", "sales_auxiliar"),
    ("inventario", "inventory_manager"),
    ("inventarioj", "inventory_auxiliar"),
    ("tesoreria", "head_of_treasury"),
    ("tesoreriaj", "auxiliar_of_treasury"),
    ("pasante", "purchasing_auxiliar"),
    ("pasante", "accounting_auxiliar"),
    ("pasante", "auxiliar_of_treasury"),
    ("pasante", "inventory_auxiliar"),
    ("pasante", "sales_auxiliar"),
    ("usuario", "purchasing_user"),
    ("usuario", "accounting_user"),
    ("usuario", "inventory_user"),
    ("usuario", "user_of_treasury"),
    ("usuario", "sales_user"),
]


def _make_unidades() -> tuple:
    """Crea instancias frescas de Unidades de Negocio."""
    return (
        Unit(name="Casa Matriz", entity="cacao", code="matriz", status="active"),
        Unit(name="Movil", entity="cacao", code="movil", status="active"),
        Unit(name="Masaya", entity="cacao", code="masaya", status="inactive"),
        Unit(name="Logistica", entity="cacao", code="logistica", status="active"),
        Unit(name="Ventas Norte", entity="cacao", code="ventas_n", status="active"),
    )


def _make_entidades() -> tuple:
    """Crea instancias frescas de Entidades."""
    return (
        Entity(
            id="01J092PXHEBF4M129A7GZZ48E2",
            code="cacao",
            company_name="Choco Sonrisas Sociedad Anonima",
            name="Choco Sonrisas",
            tax_id="J0310000000000",
            currency="NIO",
            entity_type="Sociedad",
            e_mail="info@chocoworld.com",
            web="chocoworld.com",
            phone1="+505 8456 6543",
            phone2="+505 8456 7543",
            fax="+505 8456 7545",
            enabled=True,
            default=True,
            status="default",
        ),
        Entity(
            id="01J092PXHEBF4M129A7GZZ48I2",
            code="cafe",
            company_name="Mundo Cafe Sociedad Anonima",
            name="Mundo Cafe",
            tax_id="J0310000000001",
            currency="USD",
            entity_type="Sociedad",
            e_mail="info@mundocafe.com",
            web="mundocafe.com",
            phone1="+505 8456 6542",
            phone2="+505 8456 7542",
            fax="+505 8456 7546",
            enabled=True,
            default=False,
            status="active",
        ),
        Entity(
            id="01J092PXHEBF4M129A7GZZ48A2",
            code="dulce",
            company_name="Mundo Sabor Sociedad Anonima",
            name="Dulce Sabor",
            tax_id="J0310000000002",
            currency="NIO",
            entity_type="Sociedad",
            e_mail="info@chocoworld.com",
            web="chocoworld.com",
            phone1="+505 8456 6543",
            phone2="+505 8456 7543",
            fax="+505 8456 7545",
            enabled=False,
            default=False,
            status="inactive",
        ),
    )


def _make_series() -> tuple:
    """Crea instancias frescas de Series."""
    return ()


def _make_cuentas() -> tuple:
    """Crea instancias frescas de Cuentas contables de prueba."""
    return (
        Accounts(active=True, enabled=True, entity="cacao", code="6", name="Cuenta Prueba Nivel 0", group=True, parent=None),
        Accounts(active=True, enabled=True, entity="cacao", code="6.1", name="Cuenta Prueba Nivel 1", group=True, parent="6"),
        Accounts(
            active=True, enabled=True, entity="cacao", code="6.1.1", name="Cuenta Prueba Nivel 2", group=True, parent="6.1"
        ),
        Accounts(
            active=True, enabled=True, entity="cacao", code="6.1.1.1", name="Cuenta Prueba Nivel 3", group=True, parent="6.1.1"
        ),
        Accounts(
            active=True,
            enabled=True,
            entity="cacao",
            code="6.1.1.1.1",
            name="Cuenta Prueba Nivel 4",
            group=True,
            parent="6.1.1.1",
        ),
        Accounts(
            active=True,
            enabled=True,
            entity="cacao",
            code="6.1.1.1.1.1",
            name="Cuenta Prueba Nivel 5",
            group=True,
            parent="6.1.1.1.1",
        ),
        Accounts(
            active=True,
            enabled=True,
            entity="cacao",
            code="6.1.1.1.1.1.1",
            name="Cuenta Prueba Nivel 6",
            group=True,
            parent="6.1.1.1.1.1",
        ),
        Accounts(
            active=True,
            enabled=True,
            entity="cacao",
            code="6.1.1.1.1.1.1.1",
            name="Cuenta Prueba Nivel 7",
            group=True,
            parent="6.1.1.1.1.1.1",
        ),
        Accounts(
            active=True,
            enabled=True,
            entity="cacao",
            code="6.1.1.1.1.1.1.1.1",
            name="Cuenta Prueba Nivel 8",
            group=True,
            parent="6.1.1.1.1.1.1.1",
        ),
        Accounts(
            active=True,
            enabled=True,
            entity="cacao",
            code="6.1.1.1.1.1.1.1.1.1",
            name="Cuenta Prueba Nivel 9",
            group=False,
            parent="6.1.1.1.1.1.1.1.1",
        ),
    )


def _make_centros_de_costos() -> tuple:
    """Crea instancias frescas de Centros de Costos."""
    return (
        CostCenter(
            active=True,
            default=True,
            enabled=True,
            entity="cacao",
            group=False,
            code="A00000",
            name="Centro Costos Predeterminado",
            status="active",
        ),
        CostCenter(
            active=True,
            default=True,
            enabled=True,
            entity="cacao",
            group=True,
            code="B00000",
            name="Centro Costos Nivel 0",
            status="active",
        ),
        CostCenter(
            active=True,
            default=True,
            enabled=True,
            entity="cacao",
            group=True,
            code="B00001",
            name="Centro Costos Nivel 1",
            status="active",
            parent="B00000",
        ),
        CostCenter(
            active=True,
            default=True,
            enabled=True,
            entity="cacao",
            group=True,
            code="B00011",
            name="Centro Costos Nivel 2",
            status="active",
            parent="B00001",
        ),
        CostCenter(
            active=True,
            default=True,
            enabled=True,
            entity="cacao",
            group=True,
            code="B00111",
            name="Centro Costos Nivel 3",
            status="active",
            parent="B00011",
        ),
        CostCenter(
            active=True,
            default=True,
            enabled=True,
            entity="cacao",
            group=True,
            code="B01111",
            name="Centro Costos Nivel 4",
            status="active",
            parent="B00111",
        ),
        CostCenter(
            active=True,
            default=True,
            enabled=True,
            entity="cacao",
            group=False,
            code="B11111",
            name="Centro Costos Nivel 5",
            status="active",
            parent="B01111",
        ),
        CostCenter(
            active=True,
            entity="cacao",
            code="ADM",
            name="Administración",
            group=False,
            status="active",
        ),
        CostCenter(
            active=True,
            entity="cacao",
            code="VTAS",
            name="Ventas",
            group=False,
            status="active",
        ),
        CostCenter(
            active=True,
            entity="cacao",
            code="OPS",
            name="Operaciones",
            group=False,
            status="active",
        ),
        CostCenter(
            active=True,
            default=True,
            enabled=True,
            entity="cafe",
            group=False,
            code="A00000",
            name="Centro de Costos Predeterminado",
            status="active",
        ),
        CostCenter(
            active=True,
            default=True,
            enabled=True,
            entity="dulce",
            group=False,
            code="A00000",
            name="Centro de Costos Predeterminados",
            status="active",
        ),
    )


def _make_proyectos() -> tuple:
    """Crea instancias frescas de Proyectos."""
    return (
        Project(
            enabled=True,
            entity="cacao",
            code="PTO001",
            name="Proyecto Prueba",
            start=date(year=2020, month=6, day=5),
            end=date(year=2020, month=9, day=5),
            budget=10000,
            status="open",
        ),
        Project(
            enabled=True,
            entity="dulce",
            code="PTO002",
            name="Proyecto Demo",
            start=date(year=2024, month=6, day=5),
            end=date(year=2024, month=9, day=5),
            budget=10000,
            status="open",
        ),
        Project(
            enabled=True,
            entity="cacao",
            code="PTO003",
            name="Proyecto Demostracion",
            start=date(year=2024, month=6, day=5),
            end=date(year=2024, month=9, day=5),
            budget=10000,
            status="open",
        ),
        Project(
            enabled=True,
            entity="cacao",
            code="EXPANSION",
            name="Expansión Regional",
            start=date(year=date.today().year, month=1, day=1),
            end=date(year=date.today().year, month=12, day=31),
            budget=500000,
            status="open",
        ),
    )


def _make_tasas_de_cambio() -> tuple:
    """Crea instancias frescas de Tasas de Cambio."""
    today = date.today()
    return (
        ExchangeRate(origin="USD", destination="NIO", rate=36.6243, date=today),
        ExchangeRate(origin="EUR", destination="NIO", rate=40.1234, date=today),
        ExchangeRate(origin="USD", destination="EUR", rate=1.0954, date=today),
    )


def _make_comprobantes_contables() -> list:
    """Crea definiciones de comprobantes contables dinámicos."""
    today = date.today()
    return [
        {
            "company": "cacao",
            "posting_date": today.isoformat(),
            "books": ["FISC"],
            "reference": "INIT-NIO",
            "memo": "Asiento inicial en Córdobas",
            "lines": [
                {"account": "11.01.001.001", "debit": 1000, "credit": 0, "cost_center": "A00000"},
                {"account": "31.01", "debit": 0, "credit": 1000},
            ],
        },
        {
            "company": "cacao",
            "posting_date": today.isoformat(),
            "books": ["FIN"],
            "transaction_currency": "USD",
            "reference": "INIT-USD",
            "memo": "Asiento inicial en Dólares",
            "lines": [
                {"account": "11.01.001.001", "debit": 100, "credit": 0, "currency": "USD"},
                {"account": "31.01", "debit": 0, "credit": 100, "currency": "USD"},
            ],
        },
        {
            "company": "cacao",
            "posting_date": today.isoformat(),
            "books": ["MGMT"],
            "transaction_currency": "EUR",
            "reference": "INIT-EUR",
            "memo": "Asiento inicial en Euros",
            "lines": [
                {"account": "11.01.001.001", "debit": 50, "credit": 0, "currency": "EUR"},
                {"account": "31.01", "debit": 0, "credit": 50, "currency": "EUR"},
            ],
        },
        {
            "company": "cacao",
            "posting_date": today.isoformat(),
            "books": ["FISC", "FIN", "MGMT"],
            "transaction_currency": "NIO",
            "reference": "MULTI-BOOK-NIO",
            "memo": "Asiento multi-libro con conversión desde Córdobas",
            "lines": [
                {"account": "11.01.001.001", "debit": 10, "credit": 0, "currency": "NIO"},
                {"account": "31.01", "debit": 0, "credit": 10, "currency": "NIO"},
            ],
        },
    ]


def _make_recurring_templates() -> list:
    """Crea definiciones de plantillas recurrentes."""
    today = date.today()
    return [
        {
            "data": {
                "code": "RENT-MONTHLY",
                "company": "cacao",
                "name": "Pago de Renta Mensual",
                "description": "Plantilla para pago recurrente de renta",
                "start_date": today,
                "end_date": date(today.year, 12, 31),
                "frequency": "monthly",
                "books": ["FISC"],
            },
            "items": [
                {"account_code": "52.01.001", "debit": 500, "credit": 0, "cost_center": "ADM"},
                {"account_code": "11.01.001.001", "debit": 0, "credit": 500},
            ],
        }
    ]


def _make_periodos() -> tuple:
    """Crea instancias frescas de Periodos Contables."""
    return (
        AccountingPeriod(
            entity="cacao",
            name=str(datetime.now().year),
            status="open",
            enabled=False,
            start=date(year=datetime.now().year, month=1, day=1),
            end=date(year=datetime.now().year, month=12, day=31),
        ),
        AccountingPeriod(
            entity="cacao",
            name=str(int(datetime.now().year) - 1),
            status="closed",
            enabled=False,
            start=date(year=(int(datetime.now().year) - 1), month=1, day=1),
            end=date(year=(int(datetime.now().year) - 1), month=12, day=31),
        ),
    )


def _make_bancos() -> tuple:
    """Crea instancias frescas de Bancos."""
    return (
        Bank(name="Banco Nacional de Desarrollo", swift_code="BNDENI2N", is_active=True),
        Bank(name="Banco de América Central", swift_code="BANCNI2N", is_active=True),
    )


def _make_terceros() -> tuple:
    """Crea instancias frescas de Terceros."""
    return (
        Party(party_type="supplier", name="Proveedor Demo SA", comercial_name="Demo Proveedor", tax_id="P001", is_active=True),
        Party(party_type="customer", name="Cliente Demo SA", comercial_name="Demo Cliente", tax_id="C001", is_active=True),
    )


def _make_unidades_medida() -> tuple:
    """Crea instancias frescas de Unidades de Medida."""
    return (
        UOM(code="UND", name="Unidad", is_active=True),
        UOM(code="KG", name="Kilogramo", is_active=True),
        UOM(code="LT", name="Litro", is_active=True),
        UOM(code="MT", name="Metro", is_active=True),
    )


def _make_articulos() -> tuple:
    """Crea instancias frescas de Articulos."""
    return (
        Item(code="ART-001", name="Chocolate 100g", item_type="goods", is_stock_item=True, default_uom="UND", is_active=True),
        Item(
            code="SRV-001",
            name="Servicio de Entrega",
            item_type="service",
            is_stock_item=False,
            default_uom="UND",
            is_active=True,
        ),
    )


def _make_bodegas() -> tuple:
    """Crea instancias frescas de Bodegas."""
    return (
        Warehouse(code="PRINCIPAL", name="Bodega Principal", company="cacao", is_active=True),
        Warehouse(code="SUCURSAL", name="Bodega Sucursal", company="cacao", is_active=True),
    )


# Pre-built transactional documents with predictable IDs used in tests.
PURCHASE_ORDER_ID = "POR-DEMO-0000001"
PURCHASE_RECEIPT_ID = "REC-DEMO-0000001"
PURCHASE_INVOICE_ID = "FCC-DEMO-0000001"
SALES_ORDER_ID = "SOV-DEMO-0000001"
DELIVERY_NOTE_ID = "ENT-DEMO-0000001"
SALES_INVOICE_ID = "FCV-DEMO-0000001"


def _make_documentos() -> tuple:
    """Crea instancias frescas de Documentos Transaccionales."""
    return (
        PurchaseOrder(
            id=PURCHASE_ORDER_ID,
            document_no="POR-DEMO-2025-001",
            company="cacao",
            posting_date=date(2025, 1, 15),
            docstatus=1,
            remarks="Orden de compra de demostración",
        ),
        PurchaseReceipt(
            id=PURCHASE_RECEIPT_ID,
            document_no="REC-DEMO-2025-001",
            company="cacao",
            posting_date=date(2025, 1, 20),
            purchase_order_id=PURCHASE_ORDER_ID,
            docstatus=1,
            remarks="Recepción de demostración",
        ),
        SalesOrder(
            id=SALES_ORDER_ID,
            document_no="SOV-DEMO-2025-001",
            company="cacao",
            posting_date=date(2025, 1, 15),
            docstatus=1,
            remarks="Orden de venta de demostración",
        ),
        DeliveryNote(
            id=DELIVERY_NOTE_ID,
            document_no="ENT-DEMO-2025-001",
            company="cacao",
            posting_date=date(2025, 1, 22),
            sales_order_id=SALES_ORDER_ID,
            docstatus=1,
            remarks="Nota de entrega de demostración",
        ),
        PurchaseInvoice(
            id=PURCHASE_INVOICE_ID,
            document_no="FCC-DEMO-2025-001",
            company="cacao",
            posting_date=date(2025, 1, 25),
            purchase_order_id=PURCHASE_ORDER_ID,
            purchase_receipt_id=PURCHASE_RECEIPT_ID,
            grand_total=50.00,
            outstanding_amount=50.00,
            docstatus=1,
            remarks="Factura de compra de demostración",
        ),
        SalesInvoice(
            id=SALES_INVOICE_ID,
            document_no="FCV-DEMO-2025-001",
            company="cacao",
            posting_date=date(2025, 1, 25),
            sales_order_id=SALES_ORDER_ID,
            delivery_note_id=DELIVERY_NOTE_ID,
            grand_total=40.00,
            outstanding_amount=40.00,
            docstatus=1,
            remarks="Factura de venta de demostración",
        ),
    )


def _make_items_orden_compra() -> tuple:
    """Crea instancias frescas de Items de Orden de Compra."""
    return (
        PurchaseOrderItem(
            purchase_order_id=PURCHASE_ORDER_ID,
            item_code="ART-001",
            item_name="Chocolate 100g",
            qty=10,
            uom="UND",
            rate=5.00,
            amount=50.00,
        ),
    )


def _make_items_orden_venta() -> tuple:
    """Crea instancias frescas de Items de Orden de Venta."""
    return (
        SalesOrderItem(
            sales_order_id=SALES_ORDER_ID,
            item_code="ART-001",
            item_name="Chocolate 100g",
            qty=5,
            uom="UND",
            rate=8.00,
            amount=40.00,
        ),
    )


def _make_items_recepcion() -> tuple:
    """Crea instancias frescas de Items de Recepción."""
    return (
        PurchaseReceiptItem(
            purchase_receipt_id=PURCHASE_RECEIPT_ID,
            item_code="ART-001",
            item_name="Chocolate 100g",
            qty=10,
            uom="UND",
            rate=5.00,
            amount=50.00,
            warehouse="PRINCIPAL",
        ),
    )


def _make_items_factura_compra() -> tuple:
    """Crea instancias frescas de Items de Factura de Compra."""
    return (
        PurchaseInvoiceItem(
            purchase_invoice_id=PURCHASE_INVOICE_ID,
            item_code="ART-001",
            item_name="Chocolate 100g",
            qty=10,
            uom="UND",
            rate=5.00,
            amount=50.00,
        ),
    )


def _make_items_entrega() -> tuple:
    """Crea instancias frescas de Items de Nota de Entrega."""
    return (
        DeliveryNoteItem(
            delivery_note_id=DELIVERY_NOTE_ID,
            item_code="ART-001",
            item_name="Chocolate 100g",
            qty=5,
            uom="UND",
            rate=8.00,
            amount=40.00,
        ),
    )


def _make_items_factura_venta() -> tuple:
    """Crea instancias frescas de Items de Factura de Venta."""
    return (
        SalesInvoiceItem(
            sales_invoice_id=SALES_INVOICE_ID,
            item_code="ART-001",
            item_name="Chocolate 100g",
            qty=5,
            uom="UND",
            rate=8.00,
            amount=40.00,
        ),
    )
