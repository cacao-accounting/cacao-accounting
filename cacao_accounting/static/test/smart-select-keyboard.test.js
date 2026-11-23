// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
'use strict';

const { expect } = require('chai');
const { JSDOM } = require('jsdom');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function cargarComponente() {
  const dom = new JSDOM('<!doctype html><div class="ca-smart-select"><input class="ca-smart-select-input"></div>', {
    url: 'http://localhost/'
  });
  const { window } = dom;
  let factory = null;
  window.Alpine = {
    data(name, callback) {
      if (name === 'smartSelect') factory = callback;
    }
  };
  const codigo = fs.readFileSync(path.join(__dirname, '..', 'js', 'smart-select.js'), 'utf8');
  vm.runInNewContext(codigo, { window, document: window.document, Alpine: window.Alpine, console, setTimeout, clearTimeout });
  window.document.dispatchEvent(new window.Event('alpine:init'));
  const componente = factory({ endpoint: '/api/search-select' });
  componente.$el = window.document.querySelector('.ca-smart-select');
  componente.init();
  return { componente, window };
}

describe('#1976 smart select con teclado', () => {
  it('recorre las opciones con flechas y reinicia el índice', () => {
    const { componente } = cargarComponente();
    componente.open = true;
    componente.options = [{ value: 'a' }, { value: 'b' }];

    expect(componente.highlightedIndex).to.equal(-1);
    expect(componente.highlightNext()).to.equal(0);
    expect(componente.highlightNext()).to.equal(1);
    expect(componente.highlightNext()).to.equal(0);
    expect(componente.highlightPrevious()).to.equal(1);
  });

  it('selecciona la opción resaltada con Enter', () => {
    const { componente } = cargarComponente();
    componente.open = true;
    componente.options = [{ value: 'a' }, { value: 'b' }];
    let elegida = null;
    componente.selectOption = (opcion) => {
      elegida = opcion;
    };

    componente.highlightNext();
    componente.onKeydown({ key: 'Enter', preventDefault() {} });

    expect(elegida).to.deep.equal({ value: 'a' });
  });

  it('cierra el menú con Escape y no selecciona sin resaltado', () => {
    const { componente } = cargarComponente();
    componente.open = true;
    componente.options = [{ value: 'a' }];
    let elegida = null;
    componente.selectOption = (opcion) => {
      elegida = opcion;
    };

    componente.onKeydown({ key: 'Enter', preventDefault() {} });
    expect(elegida).to.equal(null);

    componente.onKeydown({ key: 'Escape', preventDefault() {} });
    expect(componente.open).to.equal(false);
    expect(componente.highlightedIndex).to.equal(-1);
  });

  it('responde a la tecla pulsada en el input', () => {
    const { componente, window } = cargarComponente();
    componente.options = [{ value: 'a' }, { value: 'b' }];
    const input = window.document.querySelector('.ca-smart-select-input');

    input.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));

    expect(componente.open).to.equal(true);
    expect(componente.highlightedIndex).to.equal(0);
  });
});
