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
