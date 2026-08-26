# Introducción

Cacao Accouting es un software contable que busca dar covertura completa y robusto a los siguientes
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

# Bitácora de desarrollo

## 2026-08-26

### Petición del usuario

Corregir fallos focalizados de esquema, navegación administrativa, reconciliación FIFO y permisos de búsqueda.

### Plan implementado

La ejecución de esquema se verificó sin `DATABASE_URL`, para mantener aisladas las pruebas SQLite. Se actualizó la
expectativa de navegación con la sección pública de seguridad y la política ACL que rechaza con HTTP 403 un filtro de
compañía no autorizado. En inventario, la reversa de una recepción ahora queda fijada a su capa de valoración original,
evitando que FIFO consuma una recepción anterior al cancelar una recepción posterior. La regresión valida que una venta
posterior conserva el coste de la capa no anulada y que Bin, SLE, SVL y GL se reconcilian.

## 2026-08-26

### Petición del usuario

Hacer visible en el panel administrativo la opción para asignar compañías a usuarios.

### Plan implementado

Se corrigió la visibilidad de la acción `Compañías` en la lista de usuarios: antes solo aparecía para
clasificación `system`, aunque el administrador (`admin`) también es un usuario interno válido. La ruta
ahora aplica la misma regla que la asignación de roles: bloquea únicamente usuarios portal (`customer` y
`supplier`). Se añadió una prueba que verifica la visibilidad y el guardado para el usuario administrador.

La columna de acciones usa ahora badges compactos para reducir el espacio horizontal ocupado por los
enlaces y conservar la misma diferenciación visual por tipo de acción.

## 2026-08-23

### Petición del usuario

Agregar un condicional para que la exportación a PDF se deshabilite en modo desktop, debido a que WeasyPrint no está disponible.

### Plan implementado

Se inspeccionó el macro `document_print_button` en `cacao_accounting/templates/macros.html` y se confirmó que `is_desktop_mode()` ya está disponible como global de Jinja. Se agregó un condicional que no renderiza el enlace de descarga PDF en Desktop Mode, conservando el enlace de vista previa/impresión. Se añadió `tests/test_printing_ui.py` para verificar que el enlace está oculto en Desktop Mode y disponible en modo cloud.

### Decisiones de diseño

- La restricción se aplica en la interfaz compartida de los botones de impresión, evitando ofrecer una acción que depende de WeasyPrint en la instalación desktop.
- La vista previa/impresión permanece disponible porque no usa la ruta de exportación PDF.

## 2026-08-24

### Petición del usuario

Asegurar que todos los checks definidos en `.github/workflows/python-package.yml` pasen; el CI en GitHub fallaba únicamente en el job `lint`.

### Plan implementado

Se ejecutaron localmente los cuatro chequeos del job lint (`flake8`, `ruff`, `pydocstyle`, `mypy`) contra `cacao_accounting/`. Solo `flake8` y `ruff` reportaron dos errores E501 por líneas demasiado largas (>127) en el bloque CSS embebido de `build_print_html` en `cacao_accounting/printing/service.py`. Se dividieron dichas líneas en literales más cortos manteniendo el CSS resultante semánticamente idéntico. Se re-ejecutaron los cuatro linters (todos aprobados) y se corrieron `tests/test_printing_service.py` y `tests/test_printing_ui.py` sin regresiones.

### Decisiones de diseño

- La corrección fue solo de formato: dividir las cadenas CSS en varias líneas concatenadas, ya que los saltos de línea son whitespace válido en CSS y no alteran el HTML generado.
- No se modificó la configuración de linters ni se relajaron reglas para preservar los umbrales de calidad del CI.

### Petición del usuario

Realizar una auditoría exhaustiva previa a la primera versión alpha de Source-to-Pay, Order-to-Cash, Record-to-Report, bancos e inventarios, buscando errores reproducibles de cálculo o lógica de negocio. El sistema opera con múltiples libros y monedas, y los ledgers publicados son append-only: solo pueden anularse.

### Plan implementado

Se revisaron los flujos de pagos, notas de compra/venta, conversiones por libro, conciliación bancaria, pronóstico de efectivo, inventario y cancelaciones. Se corrigió una validación de Source-to-Pay: una nota de crédito o devolución de compra retrodatada ya no puede ignorar pagos posteriores y exceder el saldo vivo de la factura. La corrección quedó acompañada por una prueba de regresión y un commit semántico con sign-off.

Se ejecutaron pruebas focalizadas de los dominios auditados, incluyendo multilibro/multimoneda, sin ejecutar la suite completa.

### Decisiones de diseño

- Los saldos de documentos se validan contra su saldo transaccional vivo; la fecha retroactiva no puede reabrir un importe ya liquidado.
- Cada libro conserva su propia moneda funcional y conversión histórica; no se asume que el importe base de la entidad sea válido para otros libros.
- Los asientos GL y movimientos de stock publicados se conservan append-only. Las cancelaciones se representan mediante contrapartidas y el marcado de anulación del original, nunca por borrado o reescritura.

## 2026-08-25

### Petición del usuario

Continuar la auditoría exhaustiva del proyecto, identificar errores reproducibles de cálculo y lógica de negocio, y corregir cada uno mediante commits semánticos firmados.

### Plan implementado

Se auditó el motor de costos de importación. Se detectó que un cargo distinto de cero prorrateado con una base total igual a cero (por ejemplo, por peso cuando ningún artículo tiene peso) generaba participaciones de cero y el ajuste de residuo asignaba el 100 % del cargo a la última línea. Se añadió una validación de base positiva por método de prorrateo antes de calcular asignaciones, junto con una prueba de regresión que reproduce el caso de dos artículos sin peso y un flete de 30.

### Decisiones de diseño

- No se elige una línea arbitraria ni se aplica un prorrateo alternativo implícito: la contabilización se rechaza hasta que se proporcione una base válida.
- Los cargos de valor cero siguen siendo permitidos aunque la base sea cero, porque no alteran la valoración.

### Plan implementado

Se auditó el cálculo de plantillas fiscales con impuestos incluidos en precio. Un impuesto porcentual incluido se calculaba aplicando su tasa al precio bruto, sobreestimando el impuesto; por ejemplo, 15 % de 115 devolvía 17,25 en lugar de extraer 15,00. Se corrigió la fórmula para descomponer el precio bruto por la suma de las tasas porcentuales incluidas que comparten base de cálculo. Se añadieron pruebas de regresión para un impuesto de 15 % y para dos impuestos incluidos de 10 % y 5 % sobre un total de 115.

### Decisiones de diseño

- Los impuestos fijos incluidos conservan su importe configurado; la descomposición aplica solo a tasas porcentuales.
- Las tasas incluidas se agrupan por base de cálculo, evitando que dos impuestos del mismo precio se calculen uno sobre el bruto y se inflen mutuamente.

### Plan implementado

Se detectó una segunda condición límite en el cálculo de plantillas fiscales: cuando las líneas actuales totalizaban cero, el motor usaba indistintamente `grand_total` como respaldo. En un documento editado que conservaba un total anterior, una línea gratuita podía generar impuesto sobre ese importe obsoleto. El respaldo documental ahora se utiliza únicamente cuando no hay líneas, y se añadió una prueba de regresión con una línea de importe cero y un `grand_total` histórico de 100.

### Decisiones de diseño

- Una línea existente con importe cero es información contable válida y no equivale a la ausencia de líneas.
- Se preserva el respaldo por total documental para flujos heredados que efectivamente no aportan líneas al motor.

## 2026-08-25 (auditoría funcional)

### Petición del usuario

Realizar una auditoría funcional completa del sistema (solo lectura, sin editar código) para evaluar si es best-in-class, y luego abrir issues en GitHub para los hallazgos detectados.

### Plan implementado

Se auditó en profundidad O2C (ventas), S2P (compras), bancos/tesorería, inventario, núcleo contable/fiscal, reportes y plataforma transversal (auth, admin, API, portal, flujo documental, aprobaciones, impresión, imports, frontend, CLI), contrastando contra ERPs de referencia (Odoo, ERPNext, SAP/Dynamics). El veredicto: el núcleo contable-operativo es best-in-class (GL append-only, multi-libro/multimoneda, parcialidades línea-a-línea, matching 3-way, aprobaciones anti-tamper); las brechas se concentran en capa comercial (precios/descuentos), reporting corporativo (EFE, comparativos, consolidación), trazabilidad física (lote/serie sin UI) y plataforma (MFA, API, async). Los 5 hallazgos más sensibles se re-verificaron contra el árbol actual antes de publicar. Se crearon 27 issues en GitHub (#720–#746): 6 HIGH, 19 MEDIUM y 2 LOW (checklists), siguiendo la convención del repo (`SEVERITY:` + etiquetas por módulo/severidad), cada uno con resumen, evidencia archivo:línea, impacto, sugerencia y criterios de aceptación.

### Decisiones de diseño

- Auditoría 100% de solo lectura; ningún archivo de código fue modificado.
- Hallazgos afines se agruparon en un solo issue cuando forman una unidad de trabajo coherente (p. ej. control presupuestario #728, paquete de reporting corporativo #743, endurecimiento de cuentas #739, quick wins de UX #745).
- No se usaron etiquetas del flujo QA del repo (`verified`, `needs-work`, etc.) para no interferir con su semántica de validación; solo severidad + módulo + tipo.
- Cuerpos en español y títulos en inglés con prefijo de severidad, replicando el estilo de los issues históricos del proyecto.

### Plan implementado

Se auditó la resolución de referencias durante el pago y la liquidación cambiaria. El helper de documentos de referencia solo reconocía literalmente `purchase_invoice`; una nota de crédito o débito de compra se consultaba erróneamente contra `SalesInvoice`. Se cambió la resolución para elegir `PurchaseInvoice` o `SalesInvoice` por la familia del doctype y se añadió una prueba de regresión de una nota de crédito de compra.

### Decisiones de diseño

- Las notas de compra y venta comparten sus tablas físicas con sus respectivas facturas, pero no deben cruzar de familia al resolver referencias.
- Los tipos de referencia desconocidos se omiten de forma segura en este helper, manteniendo la validación estricta de tipos en el flujo de pagos.

### Plan implementado

Se auditó el control de disponibilidad presupuestaria por dimensiones. Una validación sin unidad de negocio o proyecto sumaba todas las líneas del presupuesto, incluidas las restringidas a una dimensión concreta. Se corrigió el filtrado para que una dimensión ausente coincida solo con líneas globales y se añadió una prueba: una transacción global ya no puede consumir un presupuesto definido únicamente para un proyecto.

### Decisiones de diseño

- Las dimensiones de presupuesto se comparan de forma exacta; la ausencia de dimensión no significa “todas las dimensiones”.
- Los presupuestos globales continúan aplicando a transacciones globales, mientras que los presupuestos restringidos exigen la misma dimensión en la transacción.

### Plan implementado

Se detectó un caso adicional en la descomposición de impuestos incluidos: al combinar un cargo fijo incluido con un impuesto porcentual incluido sobre la misma base, el cargo fijo permanecía dentro de la base del porcentaje. Por ejemplo, un precio de 125 compuesto por neto 100, timbre fijo 10 e IVA 15 % devolvía IVA 16,3043. El cálculo ahora descuenta los cargos fijos incluidos de la misma base antes de extraer las tasas porcentuales. Se añadió una prueba de regresión del escenario.

### Decisiones de diseño

- El importe fijo incluido se reconoce íntegramente y no se capitaliza dentro de la base porcentual del mismo grupo de cálculo.
- La separación continúa agrupada por `calculation_base`, de modo que los cargos de otra base no afectan la descomposición.

### Plan implementado

Se auditó el motor fiscal utilizado por la vista previa y por los asientos. Este agrupaba las tasas porcentuales incluidas por la secuencia de la regla, aunque la secuencia solo define el orden de procesamiento. Dos impuestos incluidos sobre la misma base con secuencias distintas se extraían por separado y se sobreestimaban; además no descontaba cargos fijos incluidos. Se agruparon reglas incluidas por su definición de base (`base_mode`, conceptos incluidos y excluidos) y se añadió una prueba con timbre fijo 10 e IVA 15 % incluidos en un precio de 125, con secuencias distintas.

### Decisiones de diseño

- La secuencia conserva su función de orden determinista; no determina qué impuestos comparten base gravable.
- Solo se agrupan reglas con la misma definición explícita de base, preservando las dependencias de reglas acumuladas distintas.

### Plan implementado

Se comparó el alta directa de pagos con la conciliación AR/AP. La conciliación rechazaba que descuento más diferencia cambiaria fuera igual o superior al importe aplicado, pero el alta directa no contenía ese control. Así, un pago de efectivo 1 podía liquidar una factura de 100 declarando una asignación y descuento de 100. Se incorporó la misma validación antes de crear la referencia y una prueba de regresión por la ruta HTTP que confirma que la factura conserva su saldo.

### Decisiones de diseño

- Un descuento y una diferencia cambiaria no pueden consumir por completo la asignación: debe existir una porción de efectivo conciliable.
- Ambos flujos de aplicación de pagos comparten ahora el mismo límite económico para evitar resultados divergentes según la pantalla utilizada.

### Plan implementado

Se completó la auditoría de variantes del cálculo de impuestos incluidos. Las reglas fiscales permiten un importe manual incluido en precio, pero el motor solo restaba los cargos de tipo fijo antes de extraer porcentajes incluidos. Un cargo manual 15 e IVA 15 % dentro de un total de 130 calculaba IVA 16,9565 en vez de 15. El grupo de cargos monetarios incluidos ahora contempla métodos `fixed` y `manual`; la prueba de regresión verifica la descomposición neto 100, cargo 15, IVA 15.

### Decisiones de diseño

- Los métodos fijo y manual representan importes monetarios conocidos, por lo que ambos se excluyen de la base de tasas porcentuales incluidas.
- El ajuste no cambia la semántica de tasas porcentuales ni de reglas con una base diferente.

### Plan implementado

Se auditó la proyección de caja de AR/AP. El servicio filtraba las facturas solo por sus columnas cacheadas `outstanding_amount` y `base_outstanding_amount`; una factura contabilizada importada con ambas en `NULL` quedaba fuera aunque su saldo vivo fuera positivo. Se eliminó el filtro cacheado y cada factura candidata se valora con `compute_outstanding_amount`, convirtiendo después el saldo canónico a la moneda de compañía. La prueba de regresión crea una factura con vencimiento en agosto y cachés nulos, y verifica que aumenta exactamente 100 la proyección de AR.

### Decisiones de diseño

- El pronóstico usa la misma fuente de verdad de saldos que AR/AP, no un índice cacheado que puede estar incompleto.
- Los documentos liquidados se excluyen tras el cálculo canónico, por lo que ampliar la consulta no incorpora saldos cerrados.

### Plan implementado

Se auditó el cierre fiscal anual. La comprobación de períodos abiertos usaba `is_closed = False OR enabled = True`, por lo que un período correctamente cerrado pero habilitado para consulta/reportes impedía permanentemente el cierre del año. Se corrigió el criterio para considerar abierto únicamente un período con `is_closed = False`. La prueba de ciclo de cierre anual conserva el período habilitado después de cerrarlo y verifica que el comprobante de cierre se genera.

### Decisiones de diseño

- `is_closed` es la autoridad para bloquear movimientos y decidir elegibilidad de cierre; `enabled` es una bandera administrativa independiente.
- Los períodos cerrados pueden seguir disponibles para lectura y reportes sin reabrir el año fiscal.

### Plan implementado

La validación completa detectó una compatibilidad faltante en el pronóstico de caja: algunos escenarios legados de reportes exponen facturas pero no las tablas de relaciones documentales requeridas por el cálculo canónico. El pronóstico ahora intenta primero el saldo canónico; solo para objetos sin tabla ORM o ante un `OperationalError` que confirma la ausencia de `document_relation` usa el saldo persistido y, si existe, su importe base. Se mantienen la conversión histórica y la exclusión individual de facturas sin tasa de cambio.

### Decisiones de diseño

- La fuente canónica sigue teniendo prioridad en esquemas operativos completos; el respaldo no silencia otros errores de cálculo.
- El respaldo se limita a objetos no ORM o a la ausencia explícita de la tabla de relaciones, y conserva el importe base legado para no reconvertir una moneda ya expresada en la moneda de compañía.

### Plan implementado

Se auditó el motor de liquidación de pagos. Una configuración de retención superior al importe liquidado permitía que el cálculo produjera efectivo negativo sin errores; por ejemplo, una liquidación de 100 con retención de 120 devolvía efectivo -20. Se añadió un rechazo explícito antes de construir el efectivo y una prueba de regresión del escenario.

### Decisiones de diseño

- Las retenciones pueden reducir el efectivo hasta cero, pero no pueden exceder la obligación que se liquida.
- El motor devuelve un error de cálculo antes de que el orquestador genere un pro-forma, y el servicio de contabilización convierte ese error en un rechazo de la publicación.

## 2026-08-25 (EFE NIC 7)

### Petición del usuario

Implementar el issue #722: falta el Estado de Flujo de Efectivo (NIC 7) en los reportes financieros. El usuario fijó la arquitectura: configuración explícita obligatoria (sin heurísticas silenciosas), vista dedicada para mapear cada cuenta a Operación/Inversión/Financiamiento (+Efectivo), bloqueo del reporte mientras existan cuentas con movimiento sin clasificar en el período, sugerencia por account_type solo visual y alcance de validación limitado a cuentas con movimiento del período.

### Plan implementado

Se agregó el modelo `CashFlowAccountMapping` (único por compañía+cuenta, sección NIC 7). Nuevo módulo `cacao_accounting/reportes/cash_flow.py` con: resolución de mapeos, validación de cobertura (`get_cash_flow_configuration_status`, exige además al menos una cuenta clasificada como efectivo), cálculo del EFE por identidad contable (`utilidad − Δactivos + Δpasivos/patrimonio` por sección; aporte universal `−(debe−haber)` garantiza `difference == 0` contra la variación real de las cuentas de efectivo) y servicio de la vista dedicada con sugerencias no vinculantes. Ruta `/reports/cash-flow` con estado bloqueado (plantilla con pendientes + CTA a `/accounting/cash-flow-config/{company}`), export CSV/XLSX y jerarquía heredados del marco financiero existente (`cash-flow` agregado al conjunto jerárquico y etiquetas de sección en helpers). Vista dedicada GET/POST en el módulo Contabilidad con badge Configurada/Requerida/Opcional e indicador de desbloqueo. Enlaces desde la página del módulo y acciones del dashboard API. Pruebas unitarias y HTTP completas (`tests/test_cash_flow_statement.py`, 6 casos incluidos cuadre exacto, override entre secciones y flujo HTTP de desbloqueo).

### Decisiones de diseño

- Catálogo contable ≠ presentación: el GL registra hechos y la tabla de mapeo decide cómo se presentan; nada se deduce en silencio.
- El reporte solo honra compañía/libro/período: filtros de dimensión romperían la identidad contable del cuadre.
- Excluye anulados, reversas y cierres fiscales (mismo universo que balanza/estado de resultados por defecto).
- La validación cubre cuentas con movimiento neto en la ventana; una cuenta nueva con movimiento vuelve a bloquear hasta clasificarse (guard auditable).
- La utilidad proviene de cuentas P&L aunque estén sin mapear; su clasificación explícita se ignora a propósito.
- Fase 2 fuera de alcance: método directo, efecto cambiario multimoneda, líneas personalizadas/copiables entre compañías.

### Plan implementado

Se completó la ruta de pago totalmente retenido solicitada durante la auditoría. El alta ahora admite efectivo cero únicamente en pagos o cobros con referencias aplicadas; valida que el importe aplicado esté cubierto por efectivo, descuentos/diferencia de cambio y las retenciones fiscales canónicas. El constructor contable y el posting aceptan ese caso, y el mapeador genera solo la contrapartida de tercero y la retención, sin movimiento bancario. La interfaz usa el total aplicado como base de la retención y no bloquea el envío cuando el efectivo es cero y la retención lo cubre.

### Decisiones de diseño

- Un pago de efectivo cero sin documentos liquidados sigue rechazado; no se permite crear anticipos ni pagos vacíos usando esta excepción.
- La validación se apoya en las líneas fiscales canonicalizadas y persistidas, no en el resumen calculado por el navegador.
- El efectivo bancario no se crea artificialmente: una liquidación cubierta íntegramente por retenciones publica únicamente las cuentas por pagar/cobrar y de retenciones.

### Plan implementado

Se auditó el posting de transferencias de inventario. Una transferencia cuyo origen y destino eran la misma bodega era aceptada: consumía capas FIFO y las recreaba al final de la cola, sin movimiento físico pero alterando la secuencia usada para valorar futuras salidas. Se añadió una validación previa que exige bodegas distintas y una prueba de regresión que confirma el rechazo; la prueba existente de transferencia válida continúa aprobando.

### Decisiones de diseño

- Un traslado interno requiere un cambio físico de bodega; la corrección no intenta normalizarlo como ajuste ni como movimiento nulo.
- El rechazo ocurre antes del consumo de capas de valoración, preservando el orden FIFO y el valor histórico de inventario.

### Plan implementado

Se auditó el filtrado de retenciones en el orquestador de liquidaciones. Este aceptaba indistintamente los alias heredados `payment` y `collection` para cualquier liquidación. En consecuencia, un pago a proveedor de 100 con una retención exclusiva de cobro al 10 % calculaba erróneamente efectivo de 90. Se separaron los eventos válidos por dirección y se añadió una prueba de regresión.

### Decisiones de diseño

- Los alias heredados permanecen compatibles, pero `payment` solo aplica a pagos y `collection` solo a cobros.
- El evento explícito (`payment_confirmed`, `collection_confirmed` o `refund_confirmed`) sigue siendo la autoridad primaria para las reglas modernas.
- En reembolsos, la compatibilidad heredada sigue el sentido de caja: reembolso a cliente usa `payment`; reembolso de proveedor usa `collection`.

### Plan implementado

Se auditó la aplicación de pagos a documentos multimoneda importados. Una factura extranjera con `exchange_rate = 0` pasaba la validación y varias rutas la trataban como tasa 1 al actualizar saldos base. Se añadió una validación de tasa histórica positiva antes de aplicar la referencia y una prueba de regresión con una factura USD de tasa cero.

### Decisiones de diseño

- Los documentos en moneda de la compañía no requieren tasa; los documentos extranjeros requieren una tasa positiva antes de cualquier liquidación.
- Se rechaza la operación en el límite de referencia, antes de persistir la aplicación o modificar cachés de saldo.

### Plan implementado

Se auditó el indicador de concentración en los reportes analíticos. La salida reutilizaba la fórmula de variación entre períodos para calcular la participación de cada grupo contra el total; por ejemplo, un importe de 60 dentro de un total de 100 se exponía como -40 % en vez de 60 %. Se introdujo un cálculo específico de participación y una prueba de regresión que cubre el total ordinario y el total cero.

### Decisiones de diseño

- Las participaciones se calculan como importe dividido entre total, conservando el signo contable de ambos valores.
- Un total cero se presenta como 0 % para evitar una división indefinida y mantener la respuesta del reporte estable.

## 2026-08-26

### Petición del usuario

Atender el issue #749: «Exchange revaluation multiplies instead of dividing when converting functional to account currency», que afirma que `_bank_original_balance` multiplica en lugar de dividir al convertir saldos funcionales a la moneda de la cuenta bancaria.

### Plan implementado

Se reprodujo empíricamente el escenario exacto del issue (entidad NIO, cuenta bancaria USD, única tasa USD->NIO = 36.6243, GL de 36,624.30 sin importes en moneda de cuenta): `_bank_original_balance` devolvió 1,000.0000 USD, el valor correcto, y no los 1,341,250.45 afirmados. La premisa del issue es incorrecta: `_closing_rate(origin, destination)` normaliza la dirección del par e invierte la tasa cuando solo existe el sentido contrario, por lo que multiplicar por su resultado ya equivale a dividir entre la tasa cotizada. Aplicar la corrección sugerida (`functional_amount / rate`) introduciría exactamente el error descrito. Se agregó `test_bank_functional_only_balance_divides_inverse_exchange_pair` con los números concretos del issue (36,624.30 NIO → 1,000.00 USD; cierre 37.00 → ganancia no realizada 375.70 NIO) y la suite completa del módulo pasó 16/16.

### Decisiones de diseño

- No se modificó código de producción: la conversión actual es matemáticamente correcta bajo la convención documentada del par (origen -> destino) y está cubierta además por `test_bank_balance_converts_functional_only_gl_amounts`.
- La nueva prueba de regresión congela el escenario y los criterios de aceptación del issue para detectar si una futura refactorización de `_closing_rate` rompe la normalización de dirección.
- El único riesgo residual detectado es de datos: un par NIO->USD capturado manualmente con el valor estilo USD->NIO (36.6243 en vez de 0.0273) engaña a cualquier consumidor de la tabla; eso es validación de captura, no un defecto de esta función.

### Petición del usuario

Atender el issue #731: «MEDIUM: Purchase request cannot close when lines were ordered directly without comparison round». El cierre de una Solicitud de Compra exigía que todas sus líneas estuvieran cubiertas por un comparativo finalizado con oferta seleccionada, dejando permanentemente incerrables las PR con líneas compradas por asignación directa (sin comparativo).

### Plan implementado

Se añadió `purchase_request_direct_order_item_ids` (líneas con relación activa hacia una Orden de Compra aprobada), `purchase_request_line_closure_reasons` (motivo legible por línea: comparativo u orden directa), y `purchase_request_is_ready_to_close` como nueva compuerta de cierre que acepta cobertura por comparativo o por orden directa. La ruta de cierre y el flag `can_close` del detalle usan ahora la nueva compuerta; al cerrar se registra una entrada de auditoría por línea (`log_line_closure`, acción `closed`) con el motivo correspondiente. Además se corrigió en `audit_trail_service._doc_info` la caída por defecto a nombre de clase CamelCase (p.ej. `PurchaseRequest`) que impedía que la línea de tiempo de documentos DocBase consultada por doctype snake_case (`purchase_request`) mostrara entradas; ahora se normaliza a snake_case. Pruebas nuevas en `tests/test_purchase_request_close.py` cubren PR mixta por servicio y por HTTP, rechazo de órdenes borrador/revertidas, rechazo de cierre con línea descubierta y el tipo de documento snake_case en auditoría.

### Decisiones de diseño

- La cobertura directa exige relación `active` y Orden de Compra `docstatus == 1`: una OC borrador no compromete la compra y una OC anulada revierte sus relaciones, así que ninguna de las dos cierra la línea.
- `purchase_request_comparison_is_closed` conserva su semántica original (solo comparativos) para otros consumidores; la compuerta de cierre real es `purchase_request_is_ready_to_close`.
- Si una línea tiene comparativo finalizado y además orden directa, el motivo auditado prioriza el comparativo (`setdefault`) para reflejar la decisión de abastecimiento.
- El motivo por línea se registra como entrada de auditoría independiente (acción permitida `closed`) en lugar de un comentario único, para trazabilidad granular por línea exigida por el issue.
- La normalización snake_case en `_doc_info` no afecta modelos con columna `document_type` explícita y corrige de paso la línea de tiempo vacía en detalles de solicitudes, órdenes, asientos y demás documentos DocBase.

## 2026-08-26

### Petición del usuario

Atender el issue #729: completar el ciclo operativo de retenciones. La retención debe respetar la configuración del proveedor por compañía y aplicarse por defecto al pagar; además se requiere un certificado imprimible con validación QR y un reporte fiscal mensual de retenciones aplicadas. El reporte no debe ser un resumen agrupado por proveedor.

### Plan implementado

Se reutilizó la regla fiscal configurada en la ficha del proveedor (`CompanyParty.default_tax_rule_id`) cuando la regla es de tipo `withholding` y reconoce el evento de pago. Al pagar a un proveedor, la regla configurada reemplaza las retenciones genéricas de compañía y conserva el cálculo proporcional de pagos parciales. Se agregó `WithholdingCertificate`, emitido dentro de la misma transacción del posting, con copia inmutable de las líneas, importes y relación al pago; al anular el pago el certificado se marca anulado.

El certificado se registró como documento imprimible configurable, con plantilla predeterminada que muestra base, tasa, importe retenido, efectivo pagado y QR. Se incorporó al catálogo de validación pública y se añadió el acceso desde el detalle del pago. Se agregó `/reports/withholdings/monthly`, que lista el detalle fiscal de todos los certificados emitidos del mes seleccionado y excluye anulados, con exportación CSV/XLSX mediante el framework existente.

### Decisiones de diseño

- La configuración del proveedor es la autoridad para sus retenciones al pagar; una regla de impuesto ordinario no se interpreta silenciosamente como retención.
- El certificado se crea solo cuando existe una retención positiva en un pago a proveedor contabilizado y conserva un snapshot de sus líneas para auditoría fiscal.
- El reporte es mensual y detallado por certificado/concepto; no agrega ni sustituye la trazabilidad por proveedor.
- La impresión se mantiene configurable mediante el subsistema existente de plantillas, sin fijar el formato en una ruta especial.
- La validación QR usa el mismo mecanismo público de documentos y la anulación del pago invalida el estado operativo del certificado.

### Verificación

Las pruebas focalizadas de retenciones y liquidación pasaron 15/15; las pruebas de impresión, QR y rutas pasaron 62/62. Black y Ruff pasan para los archivos nuevos/modificados revisados.

## 2026-08-26 (continuidad y correcciones)

### Petición del usuario

Verificar los commits locales frente a los issues abiertos de GitHub, confirmar qué fixes eran correctos y corregir los fallos reproducibles encontrados. Mantener las bases de datos como entornos de desarrollo descartables y no agregar migraciones.

### Plan implementado

Se compararon los 12 commits locales contra `origin/main` y los issues abiertos. Las pruebas focalizadas cubrieron 290 casos: 287 pasaron, 2 fueron omitidos y 1 falló en la auditoría de auto-conciliación bancaria. La causa fue una incompatibilidad introducida al normalizar tipos de documento a `snake_case`: el evento se guardaba como `bank_transaction`, mientras el timeline solicitado como `BankTransaction` no lo encontraba.

Se corrigió `get_document_timeline` para consultar el tipo recibido junto con sus aliases canónico `snake_case` y legacy CamelCase. También se corrigió el `F821` detectado por Ruff en `contabilidad/forms.py` importando `gettext as _` para el mensaje de validación de clasificación.

### Decisiones de diseño

- `snake_case` permanece como formato canónico de almacenamiento; la compatibilidad se resuelve en la lectura para no reescribir auditorías existentes.
- No se agregaron migraciones ni cambios de esquema; todas las bases se consideran descartables de desarrollo.
- Se preservaron los siete archivos modificados sin commit por el usuario.

### Verificación

## 2026-08-26 (triage de issues)

### Petición del usuario

Hacer triage de los 37 issues abiertos (#720–#756) comparando contra el código fuente. Clasificar: falsos positivos, ya resueltos, necesitan trabajo, diferidos pre-beta. Aplicar comentarios y etiquetas `needs-work` / `needs-review` en GitHub.

### Plan implementado

Se analizaron los 37 issues abiertos contra el árbol de código fuente actual. Cada issue fue clasificado y etiquetado en GitHub:

**Cerrados (wontfix) — 7 issues:**
- #725 API REST: No necesitamos API pública, es consumo interno de librerías JS
- #724 MFA/TOTP: Redefinido a self-service recovery por token de un solo uso (ver needs-work)
- #723 UserBookAccess admin UI: Overhead innecesario, RBAC + acceso por compañía es suficiente
- #742 Standard costing/variances/FEFO: Fuera de alcance, Cacao Accounting no es un ERP completo
- #741 Manufacturing/BOM: Fuera de alcance, Cacao Accounting no es un ERP completo
- #740 Task queue/scheduler: Fuera de alcance, operaciones síncronas
- #739 Account security hardening: Pre-beta, no prioritario

**Ya resueltos (wontfix) — 6 issues:**
- #722 Cash flow statement: Ya implementado en `reportes/cash_flow.py`
- #721 Bank matching tolerances: Ya implementado en `reconciliation_service.py`
- #720 Batch/serial capture: Ya implementado en `transaction_form_macros.html`
- #730 Sales orders close: Ya implementado via document flow API
- #745 UX polish: Dark mode completo, portal paging parcial
- #754 Tax pricing negative base: Comportamiento correcto, bases negativas son flujo real

**Diferidos (needs-review) — 5 issues:**
- #746 Platform ergonomics: i18n framework existe, strings hardcodeados es deuda técnica post-beta
- #744 Pricing engine inactive: Price lists funcionan, descuentos no son necesarios para MVP
- #743 Financial statements comparatives: Post-beta
- #733 Financial reports memory: Performance post-beta
- #729 Withholding lifecycle: Parcialmente implementado, refinamiento post-beta

**Necesitan trabajo (needs-work) — 18 issues:**
- #756 FiscalEngine concept_amounts: goods no se actualiza después de descomposición de impuestos incluidos
- #755 Credit limit error message: Mezcla moneda de transacción y moneda base en mensaje
- #753 Purchase request edit: base_currency y exchange_rate no se recalculan en edición
- #752 Analytics _convert_to_ledger: Usa fecha exacta en vez de nearest-date
- #751 Purchase returns supplier link: target_type hardcodeado a purchase_invoice
- #750 Stock valuation rebuild: Puede perder SVLs de value-adjustment en reconciliación FIFO
- #748 Dashboard income KPI: abs() enmascara pérdidas como ingreso positivo
- #736 Accounts excluded from reports: Clasificación vacía = cuenta silenciosamente excluida
- #732 Monthly close lacks integrity checks: No valida GL balance o subledger vs GL
- #734 Fiscal year closing distorted: No valida reversals en periodos posteriores
- #727 Purchase receipt warehouse: Sin validación cross-company
- #726 Sales invoice warehouse: Auto delivery note usa item default silenciosamente
- #749 FX difference sign: Requiere validación de signa con escenario real
- #738 Inventory valuation divergence: Reporte puede divergir de FIFO remaining
- #735 Project capitalization: Abor ta batch completo en moneda mixta
- #731 Purchase request close: Ya atendido (commit local)
- #728 Budget control skipped: Default policy do_nothing es inútil sin configuración
- #724 Self-service recovery: Redefinido para implementar token de un solo uso por email

**Requiere revisión (needs-review) — 1 issue:**
- #737 Bank statement hash: Posible false positive, reference_number None puede causar falsos positivos

### Decisiones de diseño

- El sistema no ha sido lanzado ni para beta pública; muchos issues son prematuros.
- Legacy scopes son overhead que se debe evitar.
- No hay deployments que proteger (entorno pre-beta).
- Cacao Accounting no es un ERP completo; flujos MTI (BOM, manufacturing) están fuera de alcance.
- Bases negativas tienen usos prácticos (devoluciones con impuestos negativos) y no son un error.
- La API REST es de consumo interno de librerías JS, no necesita versionado ni OpenAPI.

### Verificación

Se aplicaron 37 comentarios y etiquetas en GitHub. Todos los issues del rango #720–#756 fueron procesados.

## 2026-08-26 (acceso por compañía)

### Petición del usuario

Eliminar el acceso por libro contable por ser un overhead. Mantener los roles globales para definir acciones y añadir, en paralelo, administración de compañías por usuario en Cloud. Un usuario no debe poder conocer la existencia de una compañía que no tiene asignada.

### Plan implementado

Se reemplazó `UserBookAccess` por `UserCompanyAccess`, que asigna explícitamente compañías a usuarios internos. Los roles existentes conservan el control global de módulos y acciones; las rutas y servicios ahora exigen ambas capas antes de operar. Se añadió la pantalla Cloud Administración → Usuarios → Compañías y se ocultó en Desktop.

Los listados, dashboard, endpoints de selectores y formularios de compañía usan únicamente compañías activas asignadas al usuario. Los libros contables se preservan como dimensión financiera, pero ya no autorizan ni restringen usuarios: el posting resuelve todos los libros activos de la compañía e ignora selecciones parciales heredadas.

### Decisiones de diseño

- RBAC y acceso a compañías son capas paralelas: el rol define qué puede hacer un usuario; el grant define en qué compañías.
- Los administradores conservan acceso global y los usuarios sin grant no reciben resultados que revelen compañías ajenas.
- No se agrega migración de datos porque las bases de desarrollo actuales son descartables.

### Verificación de compatibilidad

Con `DATABASE_URL` desactivada, la suite completa produjo 2.192 tests pasados, 14 fallos y 12 omitidos. Los fallos correspondían a expectativas heredadas del ACL por libro, selección parcial de libros, descubrimiento global de compañías, fixtures con permisos obsoletos y mensajes que revelaban compañías inactivas. Se actualizaron esas expectativas y la batería de regresión resultante pasó 43/43; no quedaron fallos de conexión de base de datos.
