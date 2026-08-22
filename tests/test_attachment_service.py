"""Tests for Cloud-only file attachment service and item product images."""

import io
from unittest.mock import patch

import pytest

from cacao_accounting import create_app
from cacao_accounting.attachment_service import (
    AttachmentError,
    delete_attachment,
    delete_item_image,
    get_attachment_file,
    get_item_image_file,
    list_attachments,
    upload_attachment,
    upload_item_image,
)
from cacao_accounting.database import Item, User, database
from werkzeug.datastructures import FileStorage


@pytest.fixture
def app_cloud():
    """Create test application instance in Cloud mode."""
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test-secret-key-cloud",
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        database.create_all()
        yield app
        database.session.remove()
        database.drop_all()


def test_attachment_upload_and_list_cloud(app_cloud, tmp_path):
    """Test uploading and listing attachments in Cloud mode."""
    with app_cloud.app_context():
        app_cloud.config["UPLOAD_FOLDER"] = str(tmp_path)

        file_content = b"Mock PDF quotation content"
        file_obj = FileStorage(
            stream=io.BytesIO(file_content),
            filename="quotation_123.pdf",
            content_type="application/pdf",
        )

        with patch("cacao_accounting.attachment_service.is_desktop_mode", return_value=False):
            result = upload_attachment(
                reference_type="supplier_quotation",
                reference_id="SQ-0001",
                file_storage=file_obj,
                user_id="user123",
                remarks="Cotización enviada por proveedor A",
            )

            assert result["file_name"] == "quotation_123.pdf"
            assert result["file_size"] == len(file_content)
            assert result["mime_type"] == "application/pdf"

            attachments = list_attachments("supplier_quotation", "SQ-0001")
            assert len(attachments) == 1
            assert attachments[0]["file_name"] == "quotation_123.pdf"
            assert attachments[0]["remarks"] == "Cotización enviada por proveedor A"

            file_rec, path = get_attachment_file(result["file_id"])
            assert file_rec.file_name == "quotation_123.pdf"
            assert open(path, "rb").read() == file_content


def test_attachment_delete_cloud(app_cloud, tmp_path):
    """Test deleting an attachment removes DB links and physical file."""
    with app_cloud.app_context():
        app_cloud.config["UPLOAD_FOLDER"] = str(tmp_path)

        file_obj = FileStorage(
            stream=io.BytesIO(b"Sample supplier document"),
            filename="supplier_id_card.pdf",
            content_type="application/pdf",
        )

        with patch("cacao_accounting.attachment_service.is_desktop_mode", return_value=False):
            upload_res = upload_attachment(
                reference_type="supplier",
                reference_id="SUPP-01",
                file_storage=file_obj,
                user_id="user123",
            )

            file_id = upload_res["file_id"]
            attachments = list_attachments("supplier", "SUPP-01")
            assert len(attachments) == 1

            delete_attachment(file_id, "supplier", "SUPP-01", user_id="user123")

            attachments_after = list_attachments("supplier", "SUPP-01")
            assert len(attachments_after) == 0

            with pytest.raises(AttachmentError) as exc_info:
                get_attachment_file(file_id)
            assert exc_info.value.status_code == 404


def test_desktop_mode_blocks_attachments(app_cloud):
    """Test that Desktop mode strictly blocks file upload and deletion with 403."""
    with app_cloud.app_context():
        file_obj = FileStorage(
            stream=io.BytesIO(b"Desktop test content"),
            filename="test.txt",
            content_type="text/plain",
        )

        with patch("cacao_accounting.attachment_service.is_desktop_mode", return_value=True):
            with pytest.raises(AttachmentError) as exc_info:
                upload_attachment(
                    reference_type="purchase_order",
                    reference_id="PO-001",
                    file_storage=file_obj,
                )
            assert exc_info.value.status_code == 403
            assert "modo escritorio" in str(exc_info.value)

            with pytest.raises(AttachmentError) as exc_info2:
                delete_attachment("file123", "purchase_order", "PO-001")
            assert exc_info2.value.status_code == 403


def test_item_product_image_flow_cloud(app_cloud, tmp_path):
    """Test inventory item product image upload, retrieval, and deletion in Cloud mode."""
    with app_cloud.app_context():
        app_cloud.config["UPLOAD_FOLDER"] = str(tmp_path)

        # Create sample item
        item = Item(
            code="ITEM-TEST-01",
            name="Café Orgánico 500g",
            item_type="goods",
            default_uom="KG",
        )
        database.session.add(item)
        database.session.commit()

        image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        image_obj = FileStorage(
            stream=io.BytesIO(image_bytes),
            filename="product_cafe.png",
            content_type="image/png",
        )

        with patch("cacao_accounting.attachment_service.is_desktop_mode", return_value=False):
            upload_res = upload_item_image("ITEM-TEST-01", image_obj, user_id="user123")
            assert upload_res["item_id"] == "ITEM-TEST-01"

            file_rec, img_path = get_item_image_file("ITEM-TEST-01")
            assert file_rec is not None
            assert img_path is not None
            assert open(img_path, "rb").read() == image_bytes

            # Test deleting item image
            delete_item_image("ITEM-TEST-01", user_id="user123")

            file_rec_after, path_after = get_item_image_file("ITEM-TEST-01")
            assert file_rec_after is None
            assert path_after is None


def test_item_product_image_invalid_type_and_desktop_block(app_cloud):
    """Test non-image file validation and Desktop mode blocking for product images."""
    with app_cloud.app_context():
        item = Item(
            code="ITEM-TEST-02",
            name="Harina de Maíz",
            item_type="goods",
            default_uom="KG",
        )
        database.session.add(item)
        database.session.commit()

        txt_file = FileStorage(
            stream=io.BytesIO(b"not an image"),
            filename="doc.txt",
            content_type="text/plain",
        )

        with patch("cacao_accounting.attachment_service.is_desktop_mode", return_value=False):
            with pytest.raises(AttachmentError) as exc_info:
                upload_item_image("ITEM-TEST-02", txt_file)
            assert exc_info.value.status_code == 400
            assert "Formato de imagen no permitido" in str(exc_info.value)

        image_file = FileStorage(
            stream=io.BytesIO(b"\x89PNG"),
            filename="valid.png",
            content_type="image/png",
        )

        with patch("cacao_accounting.attachment_service.is_desktop_mode", return_value=True):
            with pytest.raises(AttachmentError) as exc_info2:
                upload_item_image("ITEM-TEST-02", image_file)
            assert exc_info2.value.status_code == 403
            assert "modo escritorio" in str(exc_info2.value)


def test_api_attachment_routes(app_cloud, tmp_path):
    """Test HTTP API endpoints for attachments and product images."""
    app_cloud.config["UPLOAD_FOLDER"] = str(tmp_path)
    client = app_cloud.test_client()

    with app_cloud.app_context():
        user = User(
            user="admin_test",
            e_mail="admin@example.com",
            password=b"secret_hash",
            classification="admin",
            active=True,
        )
        database.session.add(user)

        item = Item(
            code="ITEM-API-01",
            name="Cacao en Polvo",
            item_type="goods",
            default_uom="KG",
        )
        database.session.add(item)
        database.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = user.id

        with patch("cacao_accounting.attachment_service.is_desktop_mode", return_value=False):
            # Upload attachment
            data = {
                "file": (io.BytesIO(b"Supplier Invoice PDF"), "inv_456.pdf"),
                "remarks": "Factura recibida",
            }
            res = client.post("/api/attachments/purchase_invoice/INV-001/upload", data=data, content_type="multipart/form-data")
            assert res.status_code == 201
            json_res = res.get_json()
            file_id = json_res["file_id"]

            # List attachments
            res_list = client.get("/api/attachments/purchase_invoice/INV-001")
            assert res_list.status_code == 200
            attachments_list = res_list.get_json()
            assert len(attachments_list) == 1
            assert attachments_list[0]["file_name"] == "inv_456.pdf"

            # Download attachment
            res_dl = client.get(f"/attachments/download/{file_id}")
            assert res_dl.status_code == 200
            assert res_dl.data == b"Supplier Invoice PDF"

            # Delete attachment
            res_del = client.post(f"/api/attachments/{file_id}/delete", json={"reference_type": "purchase_invoice", "reference_id": "INV-001"})
            assert res_del.status_code == 200

            # Upload Item image via API
            data_img = {
                "file": (io.BytesIO(b"\x89PNGfakeimage"), "cacao.png"),
            }
            res_img = client.post("/api/inventory/items/ITEM-API-01/image", data=data_img, content_type="multipart/form-data")
            assert res_img.status_code == 200

            # Serve Item image via API
            res_get_img = client.get("/api/inventory/items/ITEM-API-01/image")
            assert res_get_img.status_code == 200
            assert res_get_img.data == b"\x89PNGfakeimage"

            # Delete Item image via API
            res_del_img = client.post("/api/inventory/items/ITEM-API-01/image/delete")
            assert res_del_img.status_code == 200
