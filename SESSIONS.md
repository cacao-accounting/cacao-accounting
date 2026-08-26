# Bitácora de desarrollo

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
