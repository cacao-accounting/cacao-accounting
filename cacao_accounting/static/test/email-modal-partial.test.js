// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

const assert = require('assert');
const fs = require('node:fs');
const path = require('node:path');

const MODAL_TEMPLATE = path.join(__dirname, '..', '..', 'templates', 'macros.html');

function normalizeTemplate(source) {
  return source
    .replace(/\{\{\s*_\("((?:[^"\\]|\\.)*)"\)\|tojson\s*\}\}/g, (_, text) => JSON.stringify(text))
    .replace(/\{\{\s*document_type\s*\}\}/g, 'purchase_invoice')
    .replace(/\{\{\s*document\.id\s*\}\}/g, 'DOC-1')
    .replace(/\{\{\s*csrf_token\(\)\s*\}\}/g, 'token');
}

function extractComponentLiteral(normalized) {
  const markerIndex = normalized.indexOf('id="emailNotificationModal"');
  assert.ok(markerIndex >= 0, 'No se encontró el modal de correo en macros.html');
  const dataStart = normalized.indexOf('x-data="', markerIndex);
  assert.ok(dataStart > markerIndex, 'El modal no declara x-data');
  const start = dataStart + 'x-data="'.length;
  let depth = 0;
  let inString = null;
  let index = start;
  for (; index < normalized.length; index += 1) {
    const char = normalized[index];
    if (inString) {
      if (char === '\\') {
        index += 1;
        continue;
      }
      if (char === inString) inString = null;
      continue;
    }
    if (char === '"' || char === "'") {
      inString = char;
      continue;
    }
    if (char === '{') depth += 1;
    else if (char === '}') {
      depth -= 1;
      if (depth === 0) break;
    }
  }
  assert.strictEqual(depth, 0, 'El componente del modal no cierra correctamente');
  return normalized.slice(start, index + 1);
}

function loadEmailModal() {
  const source = fs.readFileSync(MODAL_TEMPLATE, 'utf8');
  const literal = extractComponentLiteral(normalizeTemplate(source));
  return new Function(`return (${literal});`)();
}

function jsonResponse(status, body) {
  return Promise.resolve({
    status,
    json: () => Promise.resolve(body),
  });
}

async function flushPromises() {
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));
}

describe('email-notification-modal', function () {
  afterEach(function () {
    delete globalThis.fetch;
    delete globalThis.document;
    delete globalThis.bootstrap;
    delete globalThis.window;
  });

  it('distingue un envío parcial y lista destinatarios atendidos y errores', async function () {
    const component = loadEmailModal();
    component.recipients = 'ok@example.com, bad@example.com';
    globalThis.fetch = () =>
      jsonResponse(207, {
        success: false,
        partial: true,
        message: 'El correo se envió parcialmente.',
        sent_count: 1,
        recipients: ['ok@example.com'],
        errors: ['bad@example.com: buzón lleno'],
      });

    component.sendEmail();
    await flushPromises();

    assert.strictEqual(component.alertType, 'warning');
    assert.ok(component.alertMessage.includes('El correo se envió parcialmente.'));
    assert.ok(component.alertMessage.includes('Enviados:'));
    assert.ok(component.alertMessage.includes('ok@example.com'));
    assert.ok(component.alertMessage.includes('Errores:'));
    assert.ok(component.alertMessage.includes('bad@example.com: buzón lleno'));
  });

  it('trata partial aunque el endpoint responda 200', async function () {
    const component = loadEmailModal();
    component.recipients = 'ok@example.com, bad@example.com';
    globalThis.fetch = () =>
      jsonResponse(200, {
        success: false,
        partial: true,
        sent_count: 1,
        recipients: ['ok@example.com'],
        errors: ['bad@example.com: rechazado'],
      });

    component.sendEmail();
    await flushPromises();

    assert.strictEqual(component.alertType, 'warning');
    assert.ok(component.alertMessage.includes('bad@example.com: rechazado'));
  });

  it('mantiene el error total cuando no se envió ningún correo', async function () {
    const component = loadEmailModal();
    component.recipients = 'bad@example.com';
    globalThis.fetch = () => jsonResponse(500, { error: 'SMTP no disponible' });

    component.sendEmail();
    await flushPromises();

    assert.strictEqual(component.alertType, 'danger');
    assert.strictEqual(component.alertMessage, 'SMTP no disponible');
  });

  it('confirma el envío completo con 200 y success', async function () {
    const component = loadEmailModal();
    component.recipients = 'ok@example.com';
    globalThis.fetch = () =>
      jsonResponse(200, { success: true, message: 'Correo enviado exitosamente.', sent_count: 1 });
    const originalSetTimeout = globalThis.setTimeout;
    globalThis.setTimeout = () => 0;
    try {
      component.sendEmail();
      await flushPromises();
    } finally {
      globalThis.setTimeout = originalSetTimeout;
    }

    assert.strictEqual(component.alertType, 'success');
    assert.strictEqual(component.alertMessage, 'Correo enviado exitosamente.');
  });
});
