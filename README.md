![Logo](https://raw.githubusercontent.com/cacao-accounting/cacao-accounting/main/cacao_accounting/static/media/Cacao%20Accounting-01.png)

# Cacao Accounting

[![CI](https://github.com/cacao-accounting/cacao-accounting/actions/workflows/python-package.yml/badge.svg?branch=main&event=push)](https://github.com/cacao-accounting/cacao-accounting/actions/workflows/python-package.yml)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=cacao-accounting_cacao-accounting&metric=alert_status)](https://sonarcloud.io/dashboard?id=cacao-accounting_cacao-accounting)
[![Coverage Status](https://coveralls.io/repos/github/cacao-accounting/cacao-accounting/badge.svg?branch=main)](https://coveralls.io/github/cacao-accounting/cacao-accounting?branch=main)
![PyPI - License](https://img.shields.io/pypi/l/cacao-accounting?color=green&logo=apache)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/cacao-accounting?logo=Python&color=gree)
![PyPI - Wheel](https://img.shields.io/pypi/wheel/cacao-accounting?logo=Python)
[![Docker Repository on Quay](https://quay.io/repository/cacaoaccounting/cacaoaccounting/status "Docker Repository on Quay")](https://quay.io/repository/cacaoaccounting/cacaoaccounting)
[![Code style: black](https://img.shields.io/badge/Python%20code%20style-black-000000.svg)](https://github.com/psf/black)
[![Code style: Prettier](https://img.shields.io/badge/HTML%20code%20style-prettier-ff69b4.svg)](https://github.com/prettier/prettier)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Gitter](https://badges.gitter.im/cacao-accounting/community.svg)](https://gitter.im/cacao-accounting/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

Aplicación contable web y de escritorio para PYMEs que centraliza tesorería, compras, ventas, inventario y contabilidad general.

## Estado actual

- En desarrollo activo en la rama `main` con base en Python 3.12, Flask y SQLAlchemy.
- Arquitectura basada en blueprints por módulo: `auth`, `bancos`, `compras`, `ventas`, `inventario`, `contabilidad`, `document_flow`, `imports` y más.
- Soporte inicial de AR/AP, pagos/cobros, conciliación, inventario con valuación, impuestos y reglas fiscales, documentos operativos, importaciones masivas y trazabilidad documental.
- UI con Alpine.js, `smart-select` y diseño de formularios transaccionales compartidos.
- Internacionalización preparada para `es` y `en`.
- Calidad integrada con `black`, `ruff`, `flake8`, `mypy`, `pydocstyle` y `pytest`.

> Nota: el proyecto sigue siendo de desarrollo y no está listo para uso en producción.

## Características principales implementadas

- Cuentas por cobrar y cuentas por pagar.
- Gestión de inventario con `Stock Reconciliation` y valuación de ajustes.
- Payment entry con impuestos y cargos visibles, reglas fiscales y aplicación de referencias.
- Matriz de flujo documental (`document_flow`) para crear documentos derivados y mantener trazabilidad.
- Administración de clientes/proveedores con contactos, direcciones, grupos y cuentas por compañía.
- Motor fiscal unificado para preview y persistencia de reglas fiscales.
- Proceso de importación masiva de datos y documentos operativos.
- Revalorización cambiaria auditada y soporte para múltiples libros/ledgers.

## Uso recomendado para desarrolladores

- Crear un entorno virtual: `python -m venv .venv`
- Activar el entorno: `source .venv/bin/activate`
- Instalar dependencias: `pip install -r requirements.txt`
- Para habilitar características en la nube (como validación MIME segura en la subida de archivos), instale las dependencias opcionales: `pip install cacao-accounting[cloud]`
- Ejecutar pruebas: `CACAO_TEST=True LOGURU_LEVEL=WARNING SECRET_KEY=ASD123kljaAddS python -m pytest -v -s --exitfirst --slow=True`

## Demo online

```
Live demo at:
URL: https://cacao-accounting.onrender.com/login
User: cacao
Password: cacao

Wait to the free render instance to wake up.
```

## Participar en el proyecto

Todos los aportes son bienvenidos. Consulta el archivo [CONTRIBUTING](https://cacao-accounting.github.io/cacao-accounting/CONTRIBUTING/) para más detalles.

## Licencia

Derechos de autor 2024 - 2026 William José Moreno Reyes

Autorizado en virtud de la Licencia de Apache, Versión 2.0 (la "Licencia"); se
prohíbe utilizar este archivo excepto en cumplimiento de la Licencia. Podrá
obtener una copia de la Licencia en:

  http://www.apache.org/licenses/LICENSE-2.0

A menos que lo exijan las leyes pertinentes o se haya establecido por escrito,
el software distribuido en virtud de la Licencia se distribuye “TAL CUAL”, SIN
GARANTÍAS NI CONDICIONES DE NINGÚN TIPO, ya sean expresas o implícitas. Véase
la Licencia para consultar el texto específico relativo a los permisos y
limitaciones establecidos en la Licencia.
