# Instrucciones 

Crear un archivo SESSIONS.md este archivo debe servir como una bitacora de desarrollo, incluye en orden cronologico
un resumen de la petición del usuario y un resumen de el plan implementado, analiza el contenido del archivo SESSIONS.md
como una fuente de contexto y de las desiciones de diseño que se han tomado y para dar continuidad a desarrollo por etapas para
no tener que planear todo desde cero y tener un continuidad en el desarrollo con un contexto completo de la evolucion del proyecto.

## Contexto

La aplicación esta desarrollada en Python y utiliza como versión minima python3.12
El backend es Flask el frontend usa alpine.js
Gestor de dependencia es pip

## Linter estaticos:

Siempre considera los siguientes controles de calidad:

- Formato con black
- Chequeo de tipos con mypy
- Chequeo estatico con ruff y flake8
- Documentación adecuada del código mediante docstrings en módulos, clases y funciones
- Pruebas unitarias con pytest

Valida la estrategia de pruebas de calidad en el directorio: .github/workflows

Los tests unitarios se ejecutan con este comando:

CACAO_TEST=True LOGURU_LEVEL=WARNING SECRET_KEY=ASD123kljaAddS python -m pytest --full --tb=line --disable-warnings --slow=True

Dado que los tests toman mucho tiempo en ejecutarse se deben ejecutar en segundo plano y guardar los resultados de las pruebas en un archivo de texto para luego analizar si hubo regresiones o todas las pruebas pasaron correctamente.

Usa siempre venv o .venv para ejecutar las pruebas de calidad.

## Covertura de codigo unitario

El codigo generado debe ir acompañado por pruebas unitarias que lo cubran apropiadamente.

## Estilo

Python: black
HTML: prettier
