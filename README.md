![Logo](https://raw.githubusercontent.com/cacao-accounting/cacao-accounting/main/cacao_accounting/static/media/Cacao%20Accounting-01.png)

# Cacao Accounting

![PyPI - License](https://img.shields.io/pypi/l/cacao-accounting?color=green&logo=apache)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/cacao-accounting?logo=Python&color=gree)
![PyPI - Wheel](https://img.shields.io/pypi/wheel/cacao-accounting?logo=Python)
[![CI](https://github.com/cacao-accounting/cacao-accounting/actions/workflows/python-package.yml/badge.svg?branch=main&event=push)](https://github.com/cacao-accounting/cacao-accounting/actions/workflows/python-package.yml)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=cacao-accounting_cacao-accounting&metric=alert_status)](https://sonarcloud.io/dashboard?id=cacao-accounting_cacao-accounting)
[![Coverage Status](https://coveralls.io/repos/github/cacao-accounting/cacao-accounting/badge.svg?branch=main)](https://coveralls.io/github/cacao-accounting/cacao-accounting?branch=main)
[![Docker Repository on Quay](https://quay.io/repository/cacaoaccounting/cacaoaccounting/status "Docker Repository on Quay")](https://quay.io/repository/cacaoaccounting/cacaoaccounting)
[![Code style: black](https://img.shields.io/badge/Python%20code%20style-black-000000.svg)](https://github.com/psf/black)
[![Code style: Prettier](https://img.shields.io/badge/HTML%20code%20style-prettier-ff69b4.svg)](https://github.com/prettier/prettier)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Gitter](https://badges.gitter.im/cacao-accounting/community.svg)](https://gitter.im/cacao-accounting/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

Aplicación contable web y de escritorio para PYMEs que centraliza tesorería, compras, ventas, inventario y contabilidad general.

## Estado actual

- En desarrollo activo sobre Python 3.12+, Flask, SQLAlchemy y Alpine.js.
- Arquitectura basada en blueprints por módulo, con servicios y repositorios para la lógica de negocio y el acceso a datos.
- El núcleo contable usa `GLEntry` como fuente única de verdad, soporta múltiples libros, multimoneda, reversas y cierre de períodos.
- Están integrados los flujos de compras (S2P), ventas (O2C), bancos, inventario, impuestos, AR/AP, importaciones masivas y trazabilidad documental.
- La interfaz usa formularios transaccionales compartidos, `smart-select`, reportes financieros/operativos y acciones derivadas administradas por `document_flow`.
- La CLI oficial `cacaoctl` administra base de datos, servidor, diagnóstico y desarrollo.
- El proyecto sigue en desarrollo y no está listo para uso en producción.

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
- Cancelaciones y reversas append-only, con reportes que excluyen los movimientos anulados por defecto.
- Docker con Caddy como proxy, Waitress como servidor WSGI y migraciones Alembic idempotentes.

## Uso recomendado para desarrolladores

- Crear un entorno virtual: `python -m venv .venv`
- Activar el entorno: `source .venv/bin/activate`
- Instalar dependencias: `pip install -r requirements.txt`
- Para habilitar características en la nube (como validación MIME segura en la subida de archivos), instale las dependencias opcionales: `pip install cacao-accounting[cloud]`
- Ejecutar pruebas: `CACAO_TEST=True LOGURU_LEVEL=WARNING SECRET_KEY=ASD123kljaAddS python -m pytest --tb=line --quiet --disable-warnings --slow=True`

## CLI - cacaoctl

`cacaoctl` es la interfaz de línea de comandos oficial para administrar Cacao Accounting.

```bash
# Crear la base de datos (idempotente)
cacaoctl db init

# Aplicar migraciones pendientes (idempotente)
cacaoctl db migrate

# Crear la base de datos con datos de ejemplo
cacaoctl db init --seed

# Recrear la base de datos; solicita confirmación si no se usa --force
cacaoctl db reset

# Eliminar la base de datos solo en desarrollo
cacaoctl db clean

# Iniciar servidor de desarrollo
cacaoctl run

# Iniciar servidor de producción (Waitress)
cacaoctl serve

# Ver estado del sistema
cacaoctl status

# Ver configuración activa
cacaoctl config

# Consola interactiva con contexto de la aplicación
cacaoctl shell

# Listar rutas registradas
cacaoctl routes
```

Las opciones globales `--env dev|test|prod`, `--verbose` y `--quiet` deben
colocarse antes del comando, por ejemplo `cacaoctl --env test db init --seed`.
`db reset` y `db clean` son operaciones destructivas; `--force` omite la
confirmación. Para el detalle completo, consulta la [documentación de cacaoctl](docs/cacaoctl.md).

### Arranque local rápido

El script [`scripts/run_server.sh`](scripts/run_server.sh) está destinado
únicamente al desarrollo local: conserva la base de datos existente, carga
datos de ejemplo solo al crearla y ejecuta `cacaoctl run` en `127.0.0.1:8080`.
Para reiniciar la base de datos explícitamente, ejecútalo con
`scripts/run_server.sh --clean`. Se pueden
personalizar `CACAO_HOST`, `CACAO_PORT`, `CACAO_USER`, `CACAO_PSWD`,
`CACAO_DATABASE_URL` y `SECRET_KEY` mediante variables de entorno. Por
defecto utiliza `cacaoaccounting.db` en la raíz del proyecto, incluso en modo
de pruebas, para que la inicialización sobreviva entre procesos.

Para un servidor WSGI usa `cacaoctl serve`. En Docker, el entrypoint ejecuta
`cacaoctl db init` y `cacaoctl db migrate` de forma idempotente antes de
arrancar la aplicación.

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
