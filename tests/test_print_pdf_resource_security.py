# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La generación de PDFs no debe solicitar recursos arbitrarios al servidor."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from cacao_accounting.printing.service import PrintService, _PrintPDFURLFetcher

DATA_SVG_URI = (
    "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxIiBoZWlnaHQ9IjEiPjwvc3ZnPg=="
)


def test_pdf_rechaza_http_y_conserva_static_local(app):
    """El PDF usa logo estático local y no contacta una URL controlada por plantilla."""
    solicitudes = []

    class ResourceHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            solicitudes.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"internal response")

        def log_message(self, *_args):
            pass

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), ResourceHandler)
    hilo = Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    base_url = f"http://127.0.0.1:{servidor.server_port}/"
    html = (
        "<html><body>"
        f'<style>@import url("{base_url}remote.css"); body {{ background-image: url("{base_url}css-image"); }}</style>'
        f'<img src="{base_url}internal-secret">'
        '<img src="/static/media/brand.svg" alt="Cacao">'
        f'<img src="{DATA_SVG_URI}">'
        "</body></html>"
    )

    try:
        with app.test_request_context("/", base_url=base_url):
            pdf = PrintService()._render_pdf_document(html)

        assert pdf.startswith(b"%PDF")
        assert solicitudes == []
    finally:
        servidor.shutdown()
        hilo.join(timeout=5)
        servidor.server_close()


def test_pdf_fetcher_entrega_svg_estatico_y_data_uri(app):
    """El fetcher conserva los recursos locales necesarios para las plantillas."""
    with app.app_context():
        fetcher = _PrintPDFURLFetcher("http://localhost/", app.static_folder)
        static_resource = fetcher("http://localhost/static/media/brand.svg")
        data_resource = fetcher(DATA_SVG_URI)
        try:
            assert b"<svg" in static_resource.read()
            assert data_resource.content_type == "image/svg+xml"
            assert b"<svg" in data_resource.read()
        finally:
            static_resource.close()
            data_resource.close()


def test_pdf_fetcher_rechaza_hosts_esquemas_y_rutas_ajenos(app):
    """Solo se admiten datos inline y archivos dentro del static local."""
    with app.app_context():
        fetcher = _PrintPDFURLFetcher("http://localhost/", app.static_folder)

        for url in (
            "https://evil.example/secret",
            "file:///etc/passwd",
            "http://localhost/admin/users",
            "http://localhost/static/../../etc/passwd",
        ):
            with pytest.raises(ValueError, match="outside the application static assets"):
                fetcher(url)
