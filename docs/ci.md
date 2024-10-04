# Pruebas unitarias

Para realizar pruebas unitarias en el proyecto se sigue la siguiente estrategía:

Hay una serie de pruebas unitarias que se deben pasar con todas las versiones
de Python soportadas. Estas pruebas cuando requieren interactuar con una base
de datos utilizan SQlite como backend: [Github action](https://github.com/cacao-accounting/cacao-accounting/actions/workflows/python-package.yml)

Se realiza una prueba automatica de covertura de codigo: [Github action](https://github.com/cacao-accounting/cacao-accounting/actions/workflows/python-coverage.yml)

Se valida que el esquema de base de base de datos sea valido ejecutandolo
en SQlite, MySQL y Postgresl: [Github action](https://github.com/cacao-accounting/cacao-accounting/actions/workflows/dbcheck.yml)

Si todas las pruebas unitarias pasan se realiza un publicación automatica a
Pypi, si la versión actual corresponde a un versión ya publicada este proceso
fallara, esto es un resultado esperado: [Github action](https://github.com/cacao-accounting/cacao-accounting/actions/workflows/publish.yml)
