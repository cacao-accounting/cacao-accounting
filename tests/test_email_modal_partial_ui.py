# SPDX-License-Identifier: Apache-2.0
"""El modal de correo debe comunicar los envíos parciales (HTTP 207) en vez de un error genérico.

El endpoint `api_document_send_email` responde 207 con `partial`, `recipients` y `errors`
cuando solo algunos destinatarios reciben el correo; la interfaz debe distinguir ese
resultado de un fallo total y mostrar qué destinatarios fueron entregados y cuáles no.
Sigue el patrón de pruebas JS en subprocesso de tests/test_10_smart_select_js.py.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from jinja2 import DictLoader, Environment

MACROS_FILE = Path(__file__).resolve().parents[1] / "cacao_accounting" / "templates" / "macros.html"


def _render_email_modal() -> str:
    """Renderiza solo la macro document_email_modal con sustitutos para sus globals."""
    loader = DictLoader(
        {
            "macros.html": MACROS_FILE.read_text(encoding="utf-8"),
            "detail_view_macros.html": "",
            "smart_select_field.html": "",
        }
    )
    env = Environment(loader=loader)
    env.globals.update(
        can_send_transaction_emails=lambda: True,
        csrf_token=lambda: "test-token",
        _=lambda text: text,
    )
    template = env.get_template("macros.html")
    document = SimpleNamespace(id="PO-EMAIL-001")
    return template.module.document_email_modal("purchase_order", document)


def _extract_alpine_data(html: str) -> str:
    """Extrae el objeto x-data del modal (sus cadenas usan comillas simples)."""
    start = html.index('x-data="') + len('x-data="')
    end = html.index("x-init=", start)
    blob = html[start:end].rstrip()
    assert blob.endswith('"'), "el atributo x-data debe cerrar antes de x-init"
    return blob[:-1]


def _run_modal_script(alpine_data: str, scenario: str, checks: str) -> None:
    """Evalúa el objeto x-data real del modal en node, ejecuta sendEmail con un fetch falso
    y corre `checks` dentro del mismo IIFE."""
    script = (
        "const data = ("
        + alpine_data
        + ");\n"
        + scenario
        + "(async () => {\n"
        + "  await data.sendEmail();\n"
        + "  // sendEmail no retorna su cadena de promesas: esperar a que el fetch resuelva.\n"
        + "  await new Promise((resolve) => setTimeout(resolve, 25));\n"
        + checks
        + "})().catch((error) => {\n"
        + "  console.error(error);\n"
        + "  process.exit(1);\n"
        + "});\n"
    )
    process = subprocess.run(
        ["node", "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise AssertionError(process.stderr or process.stdout)


def test_email_modal_reports_partial_delivery_as_warning() -> None:
    """Un 207 parcial muestra advertencia con entregados y fallidos, no un error genérico."""
    scenario = """
data.recipients = "ok@test.com, bad@test.com";
globalThis.fetch = async () => ({
  status: 207,
  json: async () => ({
    partial: true,
    message: "El correo se envió parcialmente.",
    sent_count: 1,
    recipients: ["ok@test.com"],
    errors: ["bad@test.com: mailbox unavailable"],
  }),
});
"""
    checks = """
  if (data.loading !== false) throw new Error("loading no se restableció");
  if (data.alertType !== "warning") {
    throw new Error("se esperaba warning, fue " + data.alertType + ": " + data.alertMessage);
  }
  if (!data.alertMessage.includes("ok@test.com")) {
    throw new Error("falta el destinatario entregado: " + data.alertMessage);
  }
  if (!data.alertMessage.includes("bad@test.com: mailbox unavailable")) {
    throw new Error("falta el destinatario fallido: " + data.alertMessage);
  }
"""
    _run_modal_script(_extract_alpine_data(_render_email_modal()), scenario, checks)


def test_email_modal_success_branch_keeps_auto_close() -> None:
    """Un 200 con éxito sigue mostrando el mensaje de éxito y cerrando el modal."""
    scenario = """
data.recipients = "ok@test.com";
globalThis.fetch = async () => ({
  status: 200,
  json: async () => ({
    success: true,
    message: "Correo enviado exitosamente.",
    sent_count: 1,
    recipients: ["ok@test.com"],
  }),
});
globalThis.window = { location: { reload: () => {} } };
globalThis.document = { getElementById: () => null };
globalThis.bootstrap = { Modal: { getInstance: () => ({ hide: () => {} }) } };
"""
    checks = """
  if (data.alertType !== "success") {
    throw new Error("se esperaba success, fue " + data.alertType + ": " + data.alertMessage);
  }
  if (!data.alertMessage.includes("Correo enviado exitosamente")) {
    throw new Error("mensaje de éxito inesperado: " + data.alertMessage);
  }
"""
    _run_modal_script(_extract_alpine_data(_render_email_modal()), scenario, checks)
