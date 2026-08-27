# Instrucciones 

Si la tarea en que se esta trabajando tiene un issue asociado en Github utilizar el issue como bitacora
de desarrollo de la tarea: comentarios de analisis de codigo, verificaciones, fixes propuestos, limitaciones,
decisiones de diseño. 

Las siguientes etiquetas son utiles para coordinar el trabajo con issues:

- needs-review: issue no verificado, posible falso positivo, posible duplicado, se requiere establecer
  un criterio o politica antes de continuar.
- needs-work: issue verificado sin solución aplicada o con solución parcial.
- fix-proposed: existe un commit relacionado a la tarea indicada, puede avanzar a:
  - fix-confirmed: el fix se considera apropiado.
  - needs-work: el fix se considera incompleto y requiere trabajo adicional.
- fixed: issue con una solución aceptada implementada.

Una tarea no se considera completada si no cuenta con pruebas unitarias que validen el funcionamiento
esperado del sistema y ayuden a evitar que se introduzcan regresiones a funcionalidades validadas en el
futuro.

Si no hay un issue asociado a la tarea se puede usar un archivo SESSIONS.md este archivo debe servir
como una bitacora de desarrollo, analiza SESSIONS.md como una fuente de contexto y de las decisiones
de diseño que se han tomado y para dar continuidad al desarrollo por etapas para no tener que planear
todo desde cero y tener un continuidad en el desarrollo con un contexto completo de la evolucion del proyecto.

## Contexto

Python como lenguaje principal de desarrollo.
Versión minima de python es python3.12
El backend es Flask
El frontend usa alpine.js
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

CACAO_TEST=True LOGURU_LEVEL=WARNING SECRET_KEY=ASD123kljaAddS python -m pytest --full --tb=line --disable-warnings --slow=True **test file**

Dado que los tests toman mucho tiempo en ejecutarse durante el desarrollo es aceptable ejecutar solo
los tests relativos a la tarea que se esta abordando, linters (black, ruff, flake8, mypy, pylint y 
pydocstyle) toman un tiempo razonable y deben ejecutarse siempre antes de hacer un commit.

Los cambios de deben mantener en local.

La suite completa de pruebas debe ejecutarse antes de hacer push al repositorio principal.

Solo se consideran validos cambios que han sido validados por dos agentes: un implementador y un
QA ademas de feedback del desarrollar a cargo de la tares.

Usa siempre .venv para ejecutar las pruebas de calidad.

## Cobertura de codigo unitario

El codigo generado debe ir acompañado por pruebas unitarias que lo cubran apropiadamente, minimo 90% de
cobertura en codigo nuevo generado agenticamente.

No modificar archivos de WorkFlow.

## Estilo

Python: black con un largo de fila de 127 caracteres.
HTML: prettier, cuidando que pueden haber patrones válidos de alpineJS o markup
de Jinja2 que será renderizado server side antes de llegar al cliente.

## Soporte multilang

Todas las cadenas de texto visibles al usuario deben de marcarse para traducción.

## Dependencias 

Hay que evitar agregar dependencias al proyecto, solo agregar dependencias que agreguen un valor agregado real
las dependencias deben quedar pineadas a una versión conocida como segura. 

Depender de los checks de Dependabot para actualizar versión de dependencias.

Aplicar todo medida razonable para evitar que un pip install o npm install contamine el entorno con depencias sin
estado de seguridad conocido.

Preferir dependencias con licencia OSI Aproved sin copy left.
