# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2282: el guardado de numeración bancaria comunica el conflicto al usuario.

Escenario de negocio: dos sesiones editan la numeración de la misma cuenta. El
servidor responde 409 con una instrucción de recuperación; la bandeja debe
mostrar ese mensaje sin descartar la edición local y ofrecer recargar o
reintentar. Las respuestas inesperadas no deben romper el formulario.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.bancos import routes as bank_routes
from cacao_accounting.config import configuracion
from cacao_accounting.database import Bank, BankAccount, Currency, Entity, Modules, User, UserCompanyAccess, database

CONTRASENA = "numeracion-conflicto-2026"
MENSAJE_CONFLICTO = "La configuración de numeración cambió en otra sesión. Recargue e intente de nuevo."
MENSAJE_GENERICO = "Error al guardar la configuracion."


@pytest.fixture
def numeracion_conflicto():
    """Cuenta bancaria y sesión autenticada con CSRF activo."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": True,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="cash", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J-CONFLICTO",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
                UserCompanyAccess(user_id="admin", company_code="cacao"),
            ]
        )
        database.session.flush()
        banco = Bank(name="Banco Conflicto", swift_code="TESTCONF", is_active=True)
        database.session.add(banco)
        database.session.flush()
        cuenta = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta Conflicto",
            account_no="CON-1",
            currency="NIO",
            is_active=True,
        )
        database.session.add(cuenta)
        database.session.commit()
        cuenta_id = cuenta.id

    client = application.test_client()
    pagina = client.get("/login")
    csrf = re.search(r'csrf_token[^>]*value="([^"]+)"', pagina.get_data(as_text=True))
    assert csrf is not None
    client.post(
        "/login",
        data={"usuario": "admin", "acceso": CONTRASENA, "csrf_token": csrf.group(1)},
        follow_redirects=True,
    )
    yield application, client, cuenta_id
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _token(html: str) -> str:
    coincidencia = re.search(r"X-CSRFToken':\s*'([^']+)'", html)
    assert coincidencia is not None
    return coincidencia.group(1)


DRIVER_NODE = r"""
const fs = require('fs');
const vm = require('vm');
const script = fs.readFileSync(process.argv[2], 'utf8');
const scenario = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
let reloadCalled = false;
const calls = [];
const sandbox = {
  console,
  setTimeout: () => {},
  window: { location: { reload() { reloadCalled = true; } } },
  fetch: async (url, options) => {
    calls.push({ url, method: options.method, headers: options.headers, body: options.body });
    if (scenario.networkError) throw new Error('network down');
    return {
      ok: scenario.status >= 200 && scenario.status < 300,
      status: scenario.status,
      headers: { get: () => scenario.contentType },
      json: async () => {
        if (scenario.invalidJson) throw new SyntaxError('bad json');
        return scenario.payload;
      }
    };
  }
};
vm.createContext(sandbox);
vm.runInContext(script, sandbox);
(async () => {
  const config = sandbox.numberingConfig();
  config.init();
  config.configs['pay'] = {
    payment_type: 'pay', naming_series_id: 'SER-LOCAL',
    use_external_counter: false, external_counter_id: ''
  };
  config.editing = true;
  if (scenario.action === 'reload') {
    config.reload();
  } else {
    await config.save();
  }
  process.stdout.write(JSON.stringify({
    editing: config.editing,
    errorMessage: config.errorMessage,
    conflict: config.conflict,
    savedMessage: config.savedMessage,
    localValue: config.configs['pay'].naming_series_id,
    calls,
    reloadCalled
  }));
})();
"""


def _ejecutar_js(html: str, tmp_path: Path, escenario: dict) -> dict:
    coincidencia = re.search(r"<script>\s*(function numberingConfig\(\).*?)</script>", html, re.S)
    assert coincidencia is not None
    guion = tmp_path / "numbering_config.js"
    guion.write_text(coincidencia.group(1), encoding="utf-8")
    controlador = tmp_path / "driver.js"
    controlador.write_text(DRIVER_NODE, encoding="utf-8")
    datos = tmp_path / "escenario.json"
    datos.write_text(json.dumps(escenario, ensure_ascii=False), encoding="utf-8")
    resultado = subprocess.run(
        ["node", str(controlador), str(guion), str(datos)],
        check=False,
        capture_output=True,
    )
    assert resultado.returncode == 0, resultado.stderr.decode("utf-8", errors="replace")
    return json.loads(resultado.stdout.decode("utf-8"))


def test_conflicto_409_incluye_instruccion_traducible(numeracion_conflicto, monkeypatch):
    """El servidor entrega un mensaje accionable que el cliente puede mostrar."""
    _application, client, cuenta_id = numeracion_conflicto
    pagina = client.get(f"/cash_management/bank-account/{cuenta_id}")
    token = _token(pagina.get_data(as_text=True))

    def _conflicto(_cuenta):
        raise IntegrityError("insert", {}, Exception("unique"))

    monkeypatch.setattr(bank_routes, "_save_numbering_configs", _conflicto)
    respuesta = client.post(
        f"/cash_management/bank-account/{cuenta_id}/numbering-config",
        json={"configs": [{"payment_type": "pay", "use_external_counter": False}]},
        headers={"X-CSRFToken": token},
    )

    assert respuesta.status_code == 409
    assert respuesta.get_json() == {"status": "error", "message": MENSAJE_CONFLICTO}


def test_plantilla_muestra_mensaje_como_texto_y_ofrece_recuperacion(numeracion_conflicto):
    """Sin x-html el mensaje del servidor se muestra escapado por Alpine."""
    _application, client, cuenta_id = numeracion_conflicto
    html = client.get(f"/cash_management/bank-account/{cuenta_id}").get_data(as_text=True)

    assert 'x-text="errorMessage"' in html
    assert 'x-show="conflict"' in html
    assert "Reintentar" in html
    assert "Recargar" in html
    assert "x-html" not in html
    assert "X-CSRFToken" in html
    assert "alert(" not in html


@pytest.mark.parametrize(
    ("escenario", "mensaje_esperado", "conflict_esperado"),
    [
        (
            {"status": 409, "contentType": "application/json", "payload": {"status": "error", "message": MENSAJE_CONFLICTO}},
            MENSAJE_CONFLICTO,
            True,
        ),
        (
            {"status": 400, "contentType": "application/json", "payload": {"status": "error", "message": "Serie inactiva"}},
            MENSAJE_GENERICO,
            False,
        ),
        (
            {"status": 500, "contentType": "application/json", "payload": {"status": "error", "message": "Fallo interno"}},
            MENSAJE_GENERICO,
            False,
        ),
        (
            {"status": 500, "contentType": "text/html", "payload": {}},
            MENSAJE_GENERICO,
            False,
        ),
        (
            {
                "status": 409,
                "contentType": "application/json",
                "payload": {"status": "error", "message": "</span><img src=x onerror=alert(1)>"},
            },
            "</span><img src=x onerror=alert(1)>",
            True,
        ),
        (
            {"status": 409, "contentType": "application/json", "invalidJson": True},
            MENSAJE_GENERICO,
            True,
        ),
        (
            {"status": 409, "contentType": "application/json", "payload": {"status": "error"}},
            MENSAJE_GENERICO,
            True,
        ),
        ({"networkError": True, "status": 0, "contentType": "text/plain"}, MENSAJE_GENERICO, False),
    ],
)
def test_guardado_conserva_la_edicion_ante_respuestas_adversas(
    numeracion_conflicto, tmp_path, escenario, mensaje_esperado, conflict_esperado
):
    """Ninguna respuesta adversa descarta los cambios ni allega el token."""
    _application, client, cuenta_id = numeracion_conflicto
    html = client.get(f"/cash_management/bank-account/{cuenta_id}").get_data(as_text=True)
    resultado = _ejecutar_js(html, tmp_path, escenario)

    assert resultado["errorMessage"] == mensaje_esperado
    assert resultado["conflict"] is conflict_esperado
    assert resultado["editing"] is True
    assert resultado["localValue"] == "SER-LOCAL"
    assert resultado["savedMessage"] == ""
    assert resultado["reloadCalled"] is False
    if not escenario.get("networkError"):
        assert len(resultado["calls"]) == 1
        llamada = resultado["calls"][0]
        assert llamada["method"] == "POST"
        assert llamada["headers"]["Content-Type"] == "application/json"
        assert llamada["headers"]["X-CSRFToken"]
        assert "SER-LOCAL" in llamada["body"]


def test_guardado_correcto_cierra_la_edicion(numeracion_conflicto, tmp_path):
    """El camino exitoso no se altera al añadir el manejo de conflictos."""
    _application, client, cuenta_id = numeracion_conflicto
    html = client.get(f"/cash_management/bank-account/{cuenta_id}").get_data(as_text=True)
    resultado = _ejecutar_js(html, tmp_path, {"status": 200, "contentType": "application/json", "payload": {"status": "ok"}})

    assert resultado["editing"] is False
    assert resultado["errorMessage"] == ""
    assert resultado["conflict"] is False
    assert resultado["savedMessage"] == "Configuracion guardada correctamente."


def test_recargar_es_una_accion_explicita(numeracion_conflicto, tmp_path):
    """Recargar solo ocurre cuando la persona lo solicita."""
    _application, client, cuenta_id = numeracion_conflicto
    html = client.get(f"/cash_management/bank-account/{cuenta_id}").get_data(as_text=True)

    resultado = _ejecutar_js(html, tmp_path, {"status": 409, "action": "reload"})

    assert resultado["reloadCalled"] is True
    assert resultado["calls"] == []
    assert resultado["localValue"] == "SER-LOCAL"
