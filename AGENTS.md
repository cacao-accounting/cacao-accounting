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

El archivo Docker Compose incluye Redis como cache, el sistema no puede depender del servicio de cache para funcionar,
en desktop no hay caché, el uso de cache solo debe aplicar a asuntos que hagan sentido y siempre debe ser condicional y
no fallar por falta de cache.

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

Toda tarea asociada a un Issue debe usar el formato 'Refs: ###' para facilitar triaje, no cerrar issues on push,
todo trabajo asociado a un Issue debe ser validado por al menos dos agentes que coincidan que el fix aplicado es
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
hacer commits gigantes incomprensibles e inaudibles.

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
