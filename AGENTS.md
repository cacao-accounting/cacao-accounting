# Introducción

Cacao Accounting es un software contable que busca dar cobertura completa y robusta a los siguientes
flujos de negocio:

- Order to Cash (O2C): Flujo completo del ciclo de venta.
- Source to Pay (S2P): Flujo completo del proceso de abastecimiento.
- Record to Report (R2R): Generación robusta de reportes a partir de los registros almacenados en
  el sistema
- Inventory to Fulfillment (I2F): Gestión integral de inventarios.
- Cash & Treasury Management (CTM): Gestión del efectivo en caja y bancos.

Cacao Accounting no pretende ser un ERP. La manufactura, la gestión de nóminas, los activos fijos y ámbitos similares
están fuera del alcance del proyecto.

Cacao Accounting soporta dos modos de uso:
- Modo Desktop: Limitado a una empresa y un usuario por base de datos.
- Modo Cloud: multiempresa y multiusuario, con accesos definidos por roles y acceso a compañías
  específicas.

El modo desktop se considera la base operativa del sistema y debe ser completamente funcional. El modo cloud es una
capa de funcionalidad adicional que agrega funciones útiles para entornos en la nube, como correo electrónico,
multiusuario y multimoneda.

El hecho de tener que funcionar como una aplicación de escritorio implica mantener un diseño monolítico modular, sin
depender excesivamente de patrones que solo tienen sentido en entornos en la nube. En la práctica, Cacao
Accounting Desktop solo requiere una base de datos local SQLite.

Dado que en modo desktop solo está disponible la base de datos local, hay que mantener sencillo el alcance.

El sistema es:
- Multilibro: un registro se publica en varios libros sin crear registros adicionales. Todos los módulos
  operativos (O2C, S2P, I2F, CTM) publican en todos los libros activos. Solo desde el módulo de
  contabilidad es posible seleccionar a qué libros contables afecta un registro.
- Multimoneda real (toda transacción registra la moneda de origen y la moneda de destino). La multimoneda debe
  considerar la moneda del libro de destino. Si una tasa de cambio no está disponible para la conversión,
  se debe bloquear el registro.
- El ledger contable es la fuente única de verdad. Los ledgers de Cuentas por Pagar, Cuentas por Cobrar e
  Inventario existen como extensiones del ledger financiero y deben ser reconciliables en todo momento.
- El sistema es append-only: una vez registrado, un registro no se debe eliminar; solo se permite cambiar su estado
  en caso de anulación.
- El sistema diferencia entre anulaciones (mismo período) y reversiones (distintos períodos), dado que
  las anulaciones se efectúan en el mismo período y en la misma fecha que el registro adicional. Estas, en la
  práctica, tienen efecto cero y pueden excluirse de los reportes.
- AP/AR deben llevar saldo por documento. El saldo de un cliente o proveedor debe ser la suma de todos los registros
  que, sin haber sido revertidos o anulados, no se han cerrado (es decir, no han llegado a saldo cero). Por ejemplo,
  anular un pago debe devolver el saldo de las facturas asociadas antes de aplicar el pago, pero el ledger financiero
  sí debe conservar el registro del pago original y su posterior anulación. En un momento dado, el saldo de un cliente
  o proveedor debe ser reconciliable con el saldo de todas las transacciones asociadas en el ledger financiero.
- La misma lógica aplica al inventario. El inventario no solo lleva valores monetarios, sino también bodegas, ítems,
  unidades de medida, factores de conversión, etc.
- **Política append-only:** no se borran filas de evidencia (GL/Stock/AR-AP/subledger) ni se reescriben sus
  cifras; la corrección se realiza mediante contraasientos. Cambiar el estado lógico o los saldos derivados
  (`outstanding_amount`, `unallocated_amount`, `status`) NO viola el principio y estos valores pueden seguir
  mutándose en los flujos de pago y conciliación. La cancelación (`is_cancelled`) es monotónica: solo cambia de
  `False` a `True`. Una línea del ledger cancelada queda bajo lápida de forma permanente y nunca se reactiva;
  toda corrección requiere una nueva línea append-only.

# Soporte de bases de datos:

- Tier 1: SQLite (Desktop) y PostgreSQL (Cloud). El soporte completo es obligatorio; los errores son bloqueantes.
- Tier 2: MySQL. Se prueba en CI, pero no bloquea el lanzamiento.
- Tier 3: MariaDB y MS SQL Server. No se prueban en CI.

# Uso de caché

El archivo Docker Compose incluye Redis como caché. El sistema no puede ni debe depender de que el servicio de caché
esté activo para funcionar, ya que en modo desktop no hay caché disponible. El modo desktop asume que el único servicio
disponible es la base de datos SQLite, que sirve como almacén de datos local. El uso de caché solo debe aplicarse a
asuntos pertinentes y siempre debe ser condicional; el sistema no debe fallar por falta de caché.

# Instrucciones

No tomes decisiones de negocio ni modifiques el core. Si hay dudas sobre el mejor camino a seguir, detente y consulta,
no implementes sin un entendimiento del asunto o objetivo solicitado, el core de negocio esta formado son los flujos
end to end de O2C, S2P, R2R, I2F y CTM. Estos flujos de negocios se consideran estandares a nivel de procesos empresariales
y el sistema implementar estos flujos de negocios de forma robusta, precedible, comprensible y auditable.

## Coordinación del trabajo asociado a un ticket (issue)

Si la tarea en la que se está trabajando tiene un issue asociado en GitHub, se debe utilizar ese issue como bitácora
de desarrollo:

- Comentarios de análisis de código
- Verificaciones
- Fixes propuestos
- Limitaciones
- Decisiones de diseño aprobadas por la persona desarrolladora a cargo de la tarea.

Las siguientes etiquetas son útiles para coordinar el trabajo con issues:

- needs-review: issue no verificado, posible falso positivo, posible duplicado; se requiere establecer
  un criterio o política antes de continuar.
- needs-work: issue verificado sin solución aplicada o con solución parcial o incompleta. Puede haber trabajo
  avanzado, pero no se considera finalizado y requiere iteraciones adicionales.
- fix-proposed: existe uno o más commits relacionados con la tarea indicada; puede avanzar a:
  - fix-confirmed: el fix se considera apropiado y completo; es una solución robusta y bien implementada.
  - needs-work: el fix se considera incompleto y requiere trabajo adicional.
- fixed: issue con una solución aceptada implementada.

Toda tarea asociada a un issue debe usar el formato 'Refs: ###' para facilitar el triaje. No se deben cerrar issues
al hacer push. Todo trabajo asociado a un issue debe ser validado por al menos dos agentes que coincidan en que el fix
aplicado es correcto, robusto, está correctamente cubierto por pruebas unitarias, es técnicamente válido y contempla
posibles edge cases asociados al flujo de negocio de la tarea.

Una tarea no se considera completada si no cuenta con pruebas unitarias que validen el funcionamiento
esperado del sistema y ayuden a evitar que se introduzcan regresiones a funcionalidades validadas en el
futuro.

Si no hay un issue asociado a la tarea, se puede usar un archivo SESSIONS.md como bitácora de desarrollo. Analiza
SESSIONS.md como fuente de contexto y de las decisiones de diseño que se han tomado. Úsalo para dar continuidad al
desarrollo por etapas, evitar planear todo desde cero y mantener el contexto completo de la evolución del proyecto.

**Flujo de trabajo obligatorio de agentes:**
  1. **Agente implementador:** Debe comprender íntegramente la tarea, realizar las consultas necesarias y recopilar
     el contexto relevante antes de intervenir. Su responsabilidad es implementar la solución mínima, robusta, correcta
     y coherente con la lógica de negocio, evitando cambios innecesarios y resolviendo la causa raíz del problema. Debe
     crear, modificar o ampliar las pruebas unitarias necesarias. Si existen `feedback.md` y/o `review.md`, debe atender
     sus observaciones como parte de la tarea. Antes de realizar un commit, debe ejecutar las pruebas relevantes y los
     linters exigidos por el proyecto. Normalmente los issues que este agente debe atender estan etiquetados con el tag
     `needs-work`, el tag `needs-review` indica que el trabajo aun requiere análisis adicioanal antes de implementar la
     solución requerida. Los issues asociados, debe referenciarlos en el commit utilizando `Refs: ###`.
  3. **Primer agente de QA (QA1):** Realiza una revisión estática, rigurosa e independiente del código y de la solución
     implementada. No modifica código, no ejecuta pruebas ni linters, pues estos controles corresponden al implementador.
     Debe verificar la corrección funcional, lógica de negocio en marco de los flujos de negocio O2C, S2P, R2R, I2F y CTM
     estandares, robustez, mantenibilidad, consistencia arquitectónica, casos límite, posibles regresiones y suficiencia de
     las pruebas implementadas. **Criterio de aprobación:** solo puede aprobar si la solución satisface los requisitos,
     preserva los invariantes del sistema y no presenta defectos relevantes ni riesgos sin resolver. Si aprueba, mueve el
     issue a `fix-proposed`. Si rechaza, lo mueve a `needs-work`, comenta los hallazgos en GitHub y documenta los asuntos
     pendientes en `feedback.md`, con evidencia y recomendaciones concretas.
  5. **Segundo agente de QA (QA2):** Ejecuta una segunda revisión estática, rigurosa e independiente, sin modificar código
     ni repetir pruebas o linters. No debe limitarse a aceptar las conclusiones de QA1: debe evaluar por cuenta propia la
     implementación, los requisitos, la lógica de negocio en marco de los flujos negocios O2C, S2P, R2R, I2F y CTM estandares,
     los casos límite, la cobertura funcional y los riesgos de regresión. Criterio de aprobación: únicamente puede mover el issue
     a `fix-confirmed` si confirma que la solución es correcta, completa, robusta y coherente con las reglas del proyecto, sin
     defectos bloqueantes ni observaciones pendientes. En caso contrario, debe devolverlo a `needs-work`. En ambos casos debe
     comentar su decisión y justificación en GitHub y registrar su revisión local en `review.md`.
  6. **Regla de aceptación y retroalimentación:** QA1 y QA2 deben emitir evaluaciones independientes, fundamentadas en evidencia
     y criterios técnicos verificables. Ninguna aprobación puede basarse únicamente en que las pruebas pasaron o en la conformidad
     del agente anterior. Todo rechazo debe identificar el problema, su impacto y el comportamiento esperado. Cualquier retorno
     a `needs-work` obliga al implementador a corregir los hallazgos y reiniciar el ciclo de revisión QA1 → QA2. Ningún agente debe
     cerrar issues ni realizar push sin autorización expresa, el objetivo de los agentes es asegurar que el sistema ofrezca completa,
     robusta, predecible, auditable de los flujos de negocio O2C, S2P, R2R, I2F y CTM estandares manejados por la industria.
  8. **Cierre definitivo y cuarta revisión:** El estado `fix-confirmed` no constituye una aceptación definitiva. Un issue en este
     estado puede regresar a `needs-work` si se identifican defectos, regresiones, inconsistencias o incumplimientos de los requisitos,
     siempre que la decisión esté técnicamente fundamentada y documentada mediante un comentario en GitHub. Únicamente un cuarto agente
     expresamente autorizado (QA3) o el administrador del repositorio puede mover un issue a `fixed`, después de verificar que la
     solución cumple los criterios de aceptación y que las revisiones anteriores fueron satisfactorias. Los agentes Implementador,
     QA1 y QA2 no están autorizados a establecer el estado `fixed`. Ningún cambio de estado o cambio de etiqueta debe realizarse sin
     justificación y trazabilidad.

## Contexto

Python es el lenguaje principal de desarrollo.
La versión mínima de Python es 3.12.
El backend es Flask
El frontend usa Alpine.js.
El gestor de dependencias es pip.

## Linters estáticos

Siempre considera los siguientes controles de calidad:

- Formato con black
- Chequeo de tipos con mypy
- Chequeo estático con ruff y flake8
- Documentación adecuada del código mediante docstrings en módulos, clases y funciones.
- Pruebas unitarias con pytest

Valida la estrategia de pruebas de calidad en el directorio `.github/workflows`.

Dado que los tests toman mucho tiempo en ejecutarse durante el desarrollo, es aceptable ejecutar solo
los tests relativos a la tarea que se está abordando. Los linters (black, ruff, flake8, mypy, pylint y
pydocstyle) toman un tiempo razonable y deben ejecutarse siempre antes de hacer un commit.

Los cambios deben mantenerse en local; solo la persona a cargo de la tarea puede hacer push o indicar que se haga push.

La suite completa de pruebas debe ejecutarse antes de hacer push al repositorio principal.

Respetar la identidad de Git configurada y hacer commits semánticos con sign-off. Los commits deben ser pequeños y
acotados; no hacer commits gigantes, incomprensibles e inauditables. Los commits deben tener calidad y seguir el
siguiente formato:

- Commit semántico (fix, feature, docs, refactor, release, chore).
- Línea de título de 50 caracteres.
- Separar el título del cuerpo con una línea en blanco.
- Usar lenguaje directo en el título: implementa, corrige, agrega, mejora, extiende, documenta.
- Cuerpo del issue: máximo 72 caracteres.
- El cuerpo del commit describe cómo y por qué (el diff define claramente el qué). Debe aportar contexto y servir
  como documentación del cambio.
- Cerrar siempre el commit con el sign-off apropiado.

Solo se consideran válidos los cambios que hayan sido validados por dos agentes: un implementador y un agente de QA,
además de recibir feedback del desarrollador a cargo de la tarea o una tercera ronda de validación de un agente
independiente con un contexto limpio.

Usa siempre .venv o venv para ejecutar las pruebas de calidad.

## Cobertura de código unitario

El código generado debe ir acompañado por pruebas unitarias que lo cubran apropiadamente, con un mínimo del 90 % de
cobertura en código nuevo generado agénticamente o del 85 % en código preexistente editado.

No modificar archivos de workflow.

## Estilo

Python: black con una longitud de línea de 127 caracteres.
HTML: prettier, teniendo en cuenta que puede haber patrones válidos de Alpine.js o markup
de Jinja2 que se renderizan en el servidor antes de llegar al cliente.

## Soporte multilingüe

Todas las cadenas de texto visibles para el usuario deben marcarse para traducción. El idioma base de desarrollo es
el español; las cadenas visibles para el usuario deben estar marcadas para traducción y traducidas correctamente.

Al agregar cadenas nuevas de texto visibles para el usuario, estas deben marcarse para traducción e incorporarse con
su traducción del español al inglés en `cacao_accounting/translations/en/LC_MESSAGES/messages.po`.

## Dependencias

Hay que evitar agregar dependencias al proyecto. Solo deben agregarse las que aporten un valor real y deben quedar
fijadas a una versión conocida como segura.

Depender de los checks de Dependabot para actualizar las versiones de las dependencias.

Aplicar toda medida razonable para evitar que un `pip install` o `npm install` contamine el entorno con dependencias
cuyo estado de seguridad se desconozca.

Preferir dependencias con licencia aprobada por OSI y sin copyleft.

## Autoría

Al hacer commits, respeta el autor y el correo configurados en Git local; no agregues líneas de coautoría.
Los commits deben ser revisados y firmados por una persona antes de incorporarse al repositorio, sin mezclar
la autoría de agentes de asistencia.

## Regla de calidad de pruebas

Todas las pruebas automatizadas deben ser reales, sustanciales y orientadas a validar comportamientos funcionales,
reglas de negocio, invariantes y escenarios de uso auténticos. Se prohíbe crear pruebas artificiales, triviales,
redundantes o diseñadas únicamente para incrementar métricas de cobertura. Las pruebas deben verificar resultados
esperados independientes de la implementación, utilizar datos y escenarios representativos, minimizar mocks y
ejecutar integraciones reales cuando corresponda. La prioridad es detectar defectos, regresiones e inconsistencias,
no alcanzar porcentajes de cobertura ni acumular cantidad de pruebas.

## Trabajo de terceros

Es posible que en el repositorio haya trabajo paralelo; por ningún motivo se debe revertir el trabajo realizado
por terceros. Respeta su trabajo y sé un buen vecino enfocado en la tarea actual.

## Complejidad

El código productivo (aquel dentro del directorio principal `cacao_accounting`) generado por un LLM debe analizarse,
antes de incorporarlo al proyecto, para asegurar que sea:

* Entendible y comprensible por un humano.
* Mantenible.
* Editable.

Por este motivo, el proyecto ha seleccionado **complexipy** como herramienta para medir la complejidad del código
nuevo incorporado al proyecto.

Solo se acepta código nuevo con una complejidad **igual o menor a 20**. Para verificarlo, se debe ejecutar:

`complexipy **edited-files** --max-complexity-allowed 20`

Si el código introducido supera este umbral, debe refactorizarse para reducir su complejidad y garantizar que continúe
siendo claro, mantenible y comprensible por una persona.

Al refactorizar código que supera el límite de complejidad, se deben seguir estas cinco reglas:

1. **Divide responsabilidades**
   Una función, método o clase debe tener una responsabilidad clara. Si realiza múltiples tareas independientes,
   divídelas en componentes más pequeños con nombres que expresen claramente su propósito.

2. **Reduce el anidamiento**
   Evita estructuras profundamente anidadas de `if`, `for`, `while`, `try`, etc. Utiliza retornos tempranos (*early
   returns*), cláusulas de guarda (*guard clauses*) o funciones auxiliares para mantener un flujo de ejecución simple y
   fácil de seguir. Cuando existan múltiples ramas condicionales sobre un mismo valor o estructura, prioriza match/case
   sobre largas cadenas de if/elif, siempre que mejore la legibilidad y haga explícitos los diferentes casos posibles.

3. **Extrae lógica, no la ocultes**
   Extraer código a funciones auxiliares debe mejorar la comprensión del código, no simplemente trasladar la complejidad
   a otro lugar. Cada función extraída debe representar una operación o concepto claramente identificable.

4. **Prioriza la legibilidad sobre la reducción de líneas**
   Menos líneas de código no significa necesariamente código más simple. Evita expresiones excesivamente compactas,
   condiciones difíciles de interpretar o abstracciones innecesarias. El objetivo de la refactorización es que otra
   persona pueda entender el código rápidamente.

5. **Preserva el comportamiento y verifica con pruebas**
   Una refactorización debe modificar la estructura interna del código sin alterar su comportamiento esperado. Los tests
   existentes deben continuar pasando y, cuando sea necesario, deben agregarse nuevos tests antes o durante la
   refactorización para garantizar que el comportamiento original se mantenga.

> **Regla principal:** reducir la métrica de complejidad no es el objetivo final. El objetivo es producir código que pueda
> ser leído, entendido, modificado y mantenido por una persona. La métrica es únicamente una herramienta para ayudarnos
> a conseguirlo. Si un código es correcto, fluye con naturalidad, está bien probado y sus pruebas unitarias cubren
> correctamente los caminos posibles y las posibles excepciones, es mejor mantenerlo con una complejidad de 21, 22, 23
> o 25, incluso si y solo si es realmente el mejor patrón para implementar la solución que se está trabajando.

No es necesario forzar esta regla con pruebas unitarias; aplica solo al código productivo.

## Desarrollo defensivo y validación de casos límite

Toda implementación debe diseñarse considerando escenarios más allá del flujo exitoso (*happy path*). Antes de considerar
completa una funcionalidad o corrección, los agentes deben analizar y validar, según corresponda, las condiciones límite,
entradas inválidas, transiciones de estado, operaciones concurrentes, atomicidad de las transacciones, idempotencia,
reversiones, consistencia histórica, aislamiento entre empresas y comportamiento multilibro y multimoneda.

Las pruebas deben contemplar escenarios de fallo realistas y verificar los invariantes y las reglas de negocio, en lugar de
limitarse a confirmar que la ejecución es exitosa.

## Ejecución de pruebas en paralelo

Es importante que la suite de pruebas unitarias pueda ejecutarse en paralelo usando `pytest -n auto`.
