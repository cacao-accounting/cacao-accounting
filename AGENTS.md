# Instrucciones 

## Contexto
La aplicación esta desarrollada en Python y utiiza como versión minima python3.12
El backend es Flask el frontend usa alpine.js

Las siguientes instrucciones son relevantes para el diseño de interfaces:
- `.github/instructions/global.instructions.md`
- `.github/instructions/accounting-python.instructions.md`
- `.github/instructions/transaction-forms-html.instructions.md`
- `.github/instructions/search-select-fields.instructions.md`
- `.github/instructions/reports-html.instructions.md`


Incluye siempre dentro del contexto de cada sesión los siguientes archivos:
- `modulos/contexto/core_concepts.md`
- `modulos/contabilidad.md`
- `modulos/compras.md`
- `modulos/ventas.md`
- `modulos/inventario.md`
- `modulos/setup.md`
- `modulos/relaciones.md`

Debes considerar todos esos archivos para tener el contexto completo para sesiones.

Siempre considera los siguientes controles de calidad:

- Formato con black
- Chequeo de tipos con mypy
- Chequeo estatico con ruff y flake8
- Pruebas unitarias con pytest

Los tests unitarios se ejecutan con este comando:

CACAO_TEST=True LOGURU_LEVEL=WARNING SECRET_KEY=ASD123kljaAddS python -m pytest  -v -s --exitfirst --slow=True

Usa siempre venv o .venv para ejecutar las pruebas de calidad.

Crear un archivo SESSIONS.md este archivo debe servir como una bitacora de desarrollo, incluye en orden cronologico
un resumen de la petición del usuario y un resumen de el plan implementado, analiza el contenido del archivo SESSIONS.md
como una fuente de contexto y de las desiciones de diseño que se han tomado y para dar continuidad a desarrollo por etapas para
no tener que planear todo desde cero y tener un continuidad en el desarrollo con un contexto completo de la evolucion del proyecto.

Actualiza siempre los archivos ESTADO_ACTUAL.md y PENDIENTE.md con el resultado de las iteraciones para tener siempre a
vista el estado del proyecto.
