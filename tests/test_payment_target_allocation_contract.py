"""Pruebas del contrato monetario y de trazabilidad de pagos destino."""

from datetime import date
from decimal import Decimal

from cacao_accounting.database import Party, PaymentEntry, PaymentReference, PurchaseInvoice, SalesInvoice, database
from cacao_accounting.document_flow.service import create_target_document
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.handlers.operational import get_payment_applications

FECHA = date(2026, 5, 15)
COMPANIA = "cacao"


def _factura_venta(
    customer_id: str,
    *,
    currency: str,
    total: str,
    rate: str,
    number: str,
    company: str | None = COMPANIA,
) -> SalesInvoice:
    """Crea una factura aprobada con saldo abierto representativo."""
    invoice = SalesInvoice(
        company=company,
        posting_date=FECHA,
        docstatus=1,
        document_no=number,
        customer_id=customer_id,
        customer_name="Cliente Principal SA",
        transaction_currency=currency,
        base_currency="NIO",
        exchange_rate=Decimal(rate),
        grand_total=Decimal(total),
        total=Decimal(total),
        outstanding_amount=Decimal(total),
    )
    database.session.add(invoice)
    database.session.flush()
    return invoice


def test_pago_destino_suma_importes_por_linea_y_persiste_contexto(entorno_contable):
    """La suma usa moneda de pago y cada referencia conserva su moneda origen."""
    with entorno_contable.app.app_context():
        customer_id = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one().id
        invoice_nio = _factura_venta(customer_id, currency="NIO", total="100", rate="1", number="V-NIO-1")
        invoice_usd = _factura_venta(customer_id, currency="USD", total="10", rate="36.5", number="V-USD-1")
        invoice_legacy = _factura_venta(customer_id, currency="USD", total="5", rate="36.5", number="V-LEGACY-1", company=None)
        database.session.commit()

        result = create_target_document(
            {
                "target_document_type": "payment_entry",
                "company": COMPANIA,
                "posting_date": FECHA.isoformat(),
                "payment_type": "receive",
                "party_type": "customer",
                "party_id": customer_id,
                "currency": "USD",
                "base_currency": "NIO",
                "exchange_rate": "36.5",
                "lines": [
                    {
                        "source_document_type": "sales_invoice",
                        "source_document_id": invoice_nio.id,
                        "allocated_amount": "100",
                        "payment_exchange_rate": str((Decimal("1") / Decimal("36.5")).quantize(Decimal("0.000000001"))),
                    },
                    {
                        "source_document_type": "sales_invoice",
                        "source_document_id": invoice_usd.id,
                        "allocated_amount": "10",
                    },
                    {
                        "source_document_type": "sales_invoice",
                        "source_document_id": invoice_legacy.id,
                        "allocated_amount": "5",
                    },
                ],
            },
            commit=True,
        )

        payment = database.session.get(PaymentEntry, result["target_id"])
        references = list(
            database.session.execute(
                database.select(PaymentReference).where(PaymentReference.payment_id == payment.id)
            ).scalars()
        )
        references_by_id = {reference.reference_id: reference for reference in references}

        assert Decimal(str(payment.received_amount)) == Decimal("17.7397")
        assert Decimal(str(payment.base_received_amount)) == Decimal("647.4991")
        assert Decimal(str(references_by_id[invoice_nio.id].allocated_amount)) == Decimal("100")
        assert Decimal(str(references_by_id[invoice_nio.id].payment_amount)) == Decimal("2.7397")
        assert references_by_id[invoice_nio.id].reference_type == "sales_invoice"
        assert references_by_id[invoice_nio.id].flow_source_type == "sales_invoice"
        assert references_by_id[invoice_nio.id].reference_document_no == "V-NIO-1"
        assert references_by_id[invoice_nio.id].reference_date == FECHA
        assert references_by_id[invoice_nio.id].party_type == "customer"
        assert references_by_id[invoice_nio.id].party_id == customer_id
        assert references_by_id[invoice_nio.id].company == COMPANIA
        assert references_by_id[invoice_nio.id].currency == "NIO"
        assert Decimal(str(references_by_id[invoice_nio.id].outstanding_amount_after)) == Decimal("0")
        assert Decimal(str(references_by_id[invoice_usd.id].payment_amount)) == Decimal("10.0000")
        assert Decimal(str(references_by_id[invoice_legacy.id].payment_amount)) == Decimal("5.0000")
        assert references_by_id[invoice_legacy.id].company == COMPANIA

        assert get_payment_applications.handler is not None
        query_result = get_payment_applications.handler(
            context=QueryContext(
                user_id="service",
                company_ids=[COMPANIA],
                permissions={"banking.reports.read"},
                is_service_principal=True,
            ),
            company_id=COMPANIA,
            payment_id=payment.id,
        )
        assert query_result["total_items"] == 3
        assert {row["reference_id"] for row in query_result["items"]} == {
            invoice_nio.id,
            invoice_usd.id,
            invoice_legacy.id,
        }


def test_pago_destino_registra_cuentas_por_pagar_en_moneda_del_pago(entorno_contable):
    """Los pagos a proveedor usan el mismo total convertido que sus referencias."""
    with entorno_contable.app.app_context():
        supplier_id = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one().id
        invoice = PurchaseInvoice(
            company=COMPANIA,
            posting_date=FECHA,
            docstatus=1,
            document_no="C-NIO-1",
            supplier_id=supplier_id,
            supplier_name="Proveedor Principal SA",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("365"),
            total=Decimal("365"),
            outstanding_amount=Decimal("365"),
        )
        database.session.add(invoice)
        database.session.commit()

        result = create_target_document(
            {
                "target_document_type": "payment_entry",
                "company": COMPANIA,
                "posting_date": FECHA.isoformat(),
                "payment_type": "pay",
                "party_type": "supplier",
                "party_id": supplier_id,
                "currency": "USD",
                "base_currency": "NIO",
                "exchange_rate": "36.5",
                "lines": [
                    {
                        "source_document_type": "purchase_invoice",
                        "source_document_id": invoice.id,
                        "allocated_amount": "365",
                        "payment_exchange_rate": str((Decimal("1") / Decimal("36.5")).quantize(Decimal("0.000000001"))),
                    }
                ],
            },
        )

        payment = database.session.get(PaymentEntry, result["target_id"])
        reference = database.session.execute(
            database.select(PaymentReference).where(PaymentReference.payment_id == payment.id)
        ).scalar_one()

        assert Decimal(str(payment.paid_amount)) == Decimal("10.0000")
        assert Decimal(str(payment.base_paid_amount)) == Decimal("365.0000")
        assert Decimal(str(reference.allocated_amount)) == Decimal("365")
        assert Decimal(str(reference.payment_amount)) == Decimal("10.0000")
        assert reference.company == COMPANIA
        assert reference.party_type == "supplier"
        assert reference.party_id == supplier_id
