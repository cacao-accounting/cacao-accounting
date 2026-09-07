# Introducción

Cacao Accouting es un software contable que busca dar cobertura completa y robusta a los siguientes
flujo de negocio:

- Order to Cash (O2C): Flujo completo del ciclo de venta.
- Source to Pay (S2P): Flujo completo del proceso de abastecimiento.
- Record to Report (R2R): Generación robusta de reportes a partir de los registros almacenados en
  el sistema
- Inventory to Fulfillment (I2F): Gestión integral de inventarios.
- Cash & Treasury Management (CTM): Gestión del efectivo en caja y bancos.

Cacao Accounting no pretende ser un ERP, manufactura, gestión de nominas, activo fijo y similares
estan fuera de el alcance.

Cacao Accounting soporta dos modos de uso:
- Modo Desktop: Limitado a una empresa y un usuario por base de datos.
- Modo Cloud: Multi empresa y multiusuario con acceso definidos por roles y acceso definido a compañias
  especificas.

Modo desktop se considera la base operativa del sistema, el sistema debe ser completamente funcional en
modo desktop, el modo cloud es una capa de funcionalidad adicional que agrega funciones utiles para 
entornos en la nube como: correo electronico, multi usuario, multi moneda.

El Issue (https://github.com/cacao-accounting/cacao-accounting/issues/757) tiene más análisis sobre el
alcance de modo desktop.

El hecho de tener que correr como un app de escritorio implica mantener un diseño monolítico modular, sin
depender excesivamente de patrones que hacen solo sentido en entornos en la nube. En la práctica Cacao
Accounting Desktop solo requiere una base de datos local SQLite.

Dado que en modo desktop solo esta disponible la base de datos local hay que mantener el scope sencillo.

El sistema es:
- Multilibro: un registro postea a varios libros sin crear registros adicionales, todos los modulos
  operativos (O2C, S2P, I2F, CTM) publican a todos los libros activos. Solo desde el modulo de
  contabilidad es posible seleccionar que un registro afecte libros contables especificos.
- Multimoneda real (toda transacción registra moneda origen y moneda destino) multimoneda debe
  considerar la moneda del libro destino si una tasa de cambio no esta disponible para la conversión
  bloquear el registro.
- El ledger contable es la fuente unica de verdad, los ledger de Cuentas por Pagar, Cuentas por Cobrar e
  Inventario existen como extenciones del ledger financiero y deben reconciliables en todo momento.
- El sistema es append only, una vez registrado un registro no se debe eliminar, solo se permite cambio
  de status en caso de anulaciones.
- El sistema diferencia entre anulaciones (mismo périodo) y reversiones (distintos períodos), dado que
  las anulaciones se efectuan en el mismo período y misma fecha que el registro adicional estas en la
  practica tienen efecto cero y pueden ser excluidos en reportes.
- AP/AR deben de llevar saldo por documento, el saldo de un cliente o proveedor debe ser la suma
  de todos aquellos registros que sin haber sido revertidos o anulados no se han cerrado (es decir
  no han llegado a saldo cero). Por ejemplo anular un pago debe devolver el saldo de las facturas asociadas
  antes de aplicar el pago, pero el ledger financiero si debe tener el registro del pago original y su
  posterior anulación, el saldo de un cliente o proveedor a un momento dado debe ser reconciliable con el
  saldo de todas las transacciones asociadas a ese cliente o proveedor en el ledger financiero.
- Misma lógica aplica para inventario, inventario no solo lleva valores monetarios, lleva bodegas, ítems,
  unidades de medida, factores de conversión, etc.
- **Política append-only:** no se borran filas de evidencia (GL/Stock/AR-AP/subledger) ni se reescriben sus
  cifras; la corrección va por contra-asientos. Cambiar estado lógico o saldos derivados (`outstanding_amount`,
  `unallocated_amount`, `status`, `is_cancelled`) NO viola el principio y puede seguir mutándose en los flujos
  de pago y conciliación.

# Soporte de bases de datos:

- Tier 1: SQLite (Desktop) y Postresql (Cloud). Full soporte errores son bloquers.
- Tier 2: MySQL. Se prueba en CI pero no bloquea lanzamiento.
- Tier 3: MariaDB, MS SQL Server. No sé prueban en CI.

# Uso de cache 

El archivo Docker Compose incluye Redis como cache, el sistema no puede ni debe depender del servicio de cache activo
para funcionar, esto es debido a que en modo desktop no hay caché disponible, modo desktop asume que el unico servicio
disponible es la base de datos SQLite que sirve de data store al sistema local, el uso de cache solo debe aplicarse para
asuntos que hagan sentido y siempre debe ser condicional y no fallar por falta de cache.

# Instrucciones

No tomes deciciones de negocio ni modifiques el core, si hay dudas sobre el mejor camino a seguir detente y consulta.

## Coordinación de trabajos asociados a un ticket (issue).

Si la tarea en que se esta trabajando tiene un issue asociado en Github se debe utilizar ese issue como bitacora
de desarrollo de la tarea:

- Comentarios de analisis de codigo
- Verificaciones
- Fixes propuestos
- Limitaciones
- Decisiones de diseño aprobadas por el desarrollador a cargo de la tarea.

Las siguientes etiquetas son utiles para coordinar el trabajo con issues:

- needs-review: issue no verificado, posible falso positivo, posible duplicado, se requiere establecer
  un criterio o politica antes de continuar.
- needs-work: issue verificado sin solución aplicada o con solución parcial o incompleta, puede ser trabajo
  avanzado en avanzado pero no se considera finalizado y requiere iteraciones adicionales.
- fix-proposed: existe un o mas commits relacionados a la tarea indicada, puede avanzar a:
  - fix-confirmed: el fix se considera apropiado, completo, es una solución robusta, completa y bien implementada.
  - needs-work: el fix se considera incompleto y requiere trabajo adicional.
- fixed: issue con una solución aceptada implementada.

Toda tarea asociada a un Issue debe usar el formato 'Refs: ###' para facilitar triaje, no cerrar issues on push,
todo trabajo asociado a un issue debe ser validado por al menos dos agentes que coincidan que el fix aplicado es
correcto, robusto, correctamente cubierto por pruebas unitarias, técnicamente válido y con cobertura a posibles
edge cases asociados al flujo de negocio relacionado a la tarea que se está realizando.

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

Dado que los tests toman mucho tiempo en ejecutarse durante el desarrollo es aceptable ejecutar solo
los tests relativos a la tarea que se esta abordando, linters (black, ruff, flake8, mypy, pylint y
pydocstyle) toman un tiempo razonable y deben ejecutarse siempre antes de hacer un commit.

Los cambios deben mantener en local, solo la persona a cargo de la tarea puede hacer push o indicar hacer push.

La suite completa de pruebas debe ejecutarse antes de hacer push al repositorio principal. Dado que la suite completa es
extensa y tarda mucho en ejecutarse la mejor forma de ejecutar los tests es:

- No ejecutar toda la suite en una sola corrida.
- Ejecutar los tests test file por test file:
  - Excluye tests\__init__.py y tests\conftest.py
  - No esperes a tener todos los resultados antes de corregir.
  - Corrige los issues que aparezcan segun vallan apareciendo.
  - Los lints toman un tiempo razonable y siempre deben ejecutarse.
- El archivo scripts\run_tests_by_file.sh ayuda a ejecutar los test ejecutando ese patron.

Respetar la identidad de git configurada, hacer commits semánticos con sign-off. Commits pequeños y acotados, no
hacer commits gigantes incomprensibles e inauditables, los commits debe tener calidad siguiendo el siguiente formato:

- Commit semantico (fix, feature, docs, refactor, release, chore).
- Linea de titulo de 50 caracteres.
- Separa el titulo del cuertpo con una linea en blanco.
- Usar lenguaje directo en el titulo: implementa, corrige, agrega, mejora, extiende, documenta 
- Cuerpo del issue maximo 72 characteres
- El cuerpo de commit descrique como y porque (el diff define claramente el que), el cuerpo del commit debe aportar
  contexto y servir de documentación al cambio.
- Siempre cerrar el commit con el sign-off apropiado,

Solo se consideran validos cambios que han sido validados por dos agentes: un implementador y un agente de QA,
ademas de feedback del desarrollar a cargo de la tares o un tercera ronda de validación de un agente independiente
con un contexto limpio.

Usa siempre .venv o venv para ejecutar las pruebas de calidad.

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

## Autoria

Al hacer commit respeta el autor y correo configurado en git local, no agregues lineas de co authored.
Los commits deben ser revisados y firmados por un humano antes de incorporase al repositorio sin mezclar
autoria de agentes de asistencia.


## Trabajo de terceros

Es posible que en el repositorio haya trabajo paralelo, por ningun motivo se debe revertir trabajo realizado
por terceros en el repositorio. Respetar el trabajo de terceros y ser un buen vecino enfocado en la tarea
actual.

## Complejidad

El código generado por un LLM, antes de ser incorporado al proyecto, debe ser analizado para asegurar que sea:

* Entendible y comprensible por un humano.
* Mantenible.
* Editable.

Por este motivo, el proyecto ha seleccionado **complexipy** como herramienta para medir la complejidad del código nuevo incorporado al proyecto.

Solo se acepta código nuevo con una complejidad **igual o menor a 20**. Para verificarlo, se debe ejecutar:

`complexipy **edited-files** --max-complexity-allowed 20`

Si el código introducido supera este umbral, debe ser refactorizado para reducir su complejidad y garantizar que continúe siendo claro, mantenible y comprensible por un humano.

Al refactorizar código que supera el límite de complejidad, se deben seguir estas cinco reglas:

1. **Divide responsabilidades**
   Una función, método o clase debe tener una responsabilidad clara. Si realiza múltiples tareas independientes, divídelas en componentes más pequeños con nombres que expresen claramente su propósito.

2. **Reduce el anidamiento**
   Evita estructuras profundamente anidadas de `if`, `for`, `while`, `try`, etc. Utiliza retornos tempranos (*early returns*), cláusulas de guarda (*guard clauses*) o funciones auxiliares para mantener un flujo de ejecución simple y fácil de seguir. Cuando existan múltiples ramas condicionales sobre un mismo valor o estructura, prioriza match/case sobre largas cadenas de if/elif, siempre que mejore la legibilidad y haga explícitos los diferentes casos posibles.

3. **Extrae lógica, no la ocultes**
   Extraer código a funciones auxiliares debe mejorar la comprensión del código, no simplemente trasladar la complejidad a otro lugar. Cada función extraída debe representar una operación o concepto claramente identificable.

4. **Prioriza la legibilidad sobre la reducción de líneas**
   Menos líneas de código no significa necesariamente código más simple. Evita expresiones excesivamente compactas, condiciones difíciles de interpretar o abstracciones innecesarias. El objetivo de la refactorización es que otro desarrollador pueda entender el código rápidamente.

5. **Preserva el comportamiento y verifica con pruebas**
   Una refactorización debe modificar la estructura interna del código sin alterar su comportamiento esperado. Los tests existentes deben continuar pasando y, cuando sea necesario, deben agregarse nuevos tests antes o durante la refactorización para garantizar que el comportamiento original se mantiene.

> **Regla principal:** reducir la métrica de complejidad no es el objetivo final. El objetivo es producir código que pueda ser leído, entendido, modificado y mantenido por una persona. La métrica es únicamente una herramienta para ayudarnos a conseguirlo. Si un codigo es correcto, fluye con naturalidad esta bien probado y sus pruebas unitarias cubren correctamente los caminos posibles y las posibles exepciones es mejor mantenerlo con complejidad de 21, 22, 23 o 25 incluso si y solo si es realmente el mejor patron para implementar la solucion que se esta trabajando.

