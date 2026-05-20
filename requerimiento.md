# Requerimiento técnico detallado — Submódulo de Presupuesto en Contabilidad

## 1. Objetivo

Implementar dentro del módulo existente de **Contabilidad** un submódulo de **Presupuesto** que permita administrar presupuestos financieros por compañía, libro contable y año fiscal, distribuidos por períodos contables y comparables contra la ejecución real registrada en contabilidad.

El submódulo debe permitir:

* Crear presupuestos para una compañía, libro contable y año fiscal.
* Permitir **N presupuestos por año fiscal**.
* Registrar presupuesto por:

  * cuenta contable,
  * centro de costo,
  * período contable,
  * opcionalmente unidad de negocio,
  * opcionalmente proyecto.
* Cargar presupuesto manualmente.
* Importar presupuesto desde hoja de cálculo.
* Manejar estados:

  * borrador,
  * aprobado,
  * cerrado.
* Generar el reporte **Real versus Presupuesto**.

---

# 2. Ubicación funcional

Presupuesto **no debe ser un módulo top-level**.

Debe implementarse como submódulo dentro de Contabilidad.

## 2.1 Menú requerido

Agregar dentro del menú de Contabilidad:

```text
Contabilidad
└── Presupuesto
    ├── Administrar presupuestos
    └── Real versus Presupuesto
```

## 2.2 Rutas sugeridas

```text
/contabilidad/presupuestos
/contabilidad/presupuestos/nuevo
/contabilidad/presupuestos/<id>
/contabilidad/presupuestos/<id>/editar
/contabilidad/presupuestos/<id>/importar
/contabilidad/presupuestos/<id>/aprobar
/contabilidad/presupuestos/<id>/cerrar
/contabilidad/reportes/real-vs-presupuesto
```

---

# 3. Alcance de la primera implementación

La primera versión debe incluir:

1. Administración de presupuestos.
2. Creación y edición de presupuestos en estado borrador.
3. Registro manual de líneas presupuestarias.
4. Importación desde hoja de cálculo.
5. Validación previa a inserción.
6. Aprobación de presupuesto.
7. Cierre de presupuesto.
8. Reporte Real versus Presupuesto.
9. Obtención del monto real desde líneas contables contabilizadas.

No incluir todavía:

* Control presupuestario preventivo en compras.
* Bloqueo de transacciones por exceso presupuestario.
* Ajustes presupuestarios formales.
* Versionamiento avanzado.
* Workflow de aprobación multinivel.

---

# 4. Modelo funcional

## 4.1 Presupuesto

Un presupuesto representa una planificación financiera para una compañía, libro contable y año fiscal.

Debe poder existir más de un presupuesto para el mismo año fiscal.

Ejemplos:

```text
Presupuesto Base 2026
Presupuesto Optimista 2026
Presupuesto Conservador 2026
Presupuesto Revisado Q2 2026
Presupuesto Dirección 2026
```

## 4.2 Nivel de detalle

El presupuesto se registra como líneas presupuestarias por período contable.

Nivel mínimo obligatorio:

```text
Cuenta Contable + Centro de Costo + Período Contable
```

Nivel ampliado opcional:

```text
Cuenta Contable + Centro de Costo + Unidad de Negocio + Proyecto + Período Contable
```

---

# 5. Estados del presupuesto

## 5.1 Borrador

Estado inicial.

En estado borrador se permite:

* Editar encabezado.
* Agregar líneas.
* Editar líneas.
* Eliminar líneas.
* Importar líneas desde hoja de cálculo.
* Reemplazar líneas importadas, si se define esa acción.
* Validar presupuesto.
* Aprobar presupuesto.

El presupuesto en borrador no debe considerarse presupuesto oficial.

## 5.2 Aprobado

Estado operativo.

En estado aprobado:

* No se permite editar encabezado crítico.
* No se permite agregar líneas.
* No se permite editar montos.
* No se permite eliminar líneas.
* Puede usarse en el reporte **Real versus Presupuesto**.
* Puede cerrarse.

Campos bloqueados al aprobar:

```text
company_id
ledger_id
fiscal_year_id
currency_id
budget_code
budget lines
amounts
periods
dimensions
```

## 5.3 Cerrado

Estado final.

En estado cerrado:

* No se permite edición.
* No se permite importación.
* No se permite aprobación.
* No se permite reapertura en esta primera versión.
* Sigue disponible para consulta histórica.
* Puede usarse en reportes históricos si el usuario lo selecciona explícitamente.

---

# 6. Modelo de datos requerido

## 6.1 Tabla `budgets`

Crear tabla para encabezados de presupuesto.

Campos mínimos:

```text
id
company_id
ledger_id
fiscal_year_id
budget_code
name
description
currency_id
status
created_by_id
approved_by_id
closed_by_id
created_at
updated_at
approved_at
closed_at
```

## 6.2 Campos

### `company_id`

Obligatorio.

Debe referenciar la compañía propietaria del presupuesto.

### `ledger_id`

Obligatorio.

Debe referenciar el libro contable.

El libro contable debe pertenecer a la compañía seleccionada.

### `fiscal_year_id`

Obligatorio.

Debe referenciar el año fiscal.

El año fiscal debe pertenecer o ser válido para la compañía seleccionada.

### `budget_code`

Obligatorio.

Código único del presupuesto dentro de:

```text
company_id + ledger_id + fiscal_year_id
```

Restricción sugerida:

```text
UNIQUE(company_id, ledger_id, fiscal_year_id, budget_code)
```

### `name`

Obligatorio.

Nombre descriptivo del presupuesto.

### `description`

Opcional.

Texto descriptivo.

### `currency_id`

Obligatorio.

Moneda del presupuesto.

En primera versión, se recomienda usar la moneda funcional de la compañía o la moneda base del libro contable, según el modelo existente de Cacao Accounting.

### `status`

Obligatorio.

Valores permitidos:

```text
draft
approved
closed
```

En UI:

```text
Borrador
Aprobado
Cerrado
```

### Auditoría

Campos obligatorios:

```text
created_by_id
created_at
updated_at
```

Campos condicionales:

```text
approved_by_id
approved_at
closed_by_id
closed_at
```

---

## 6.3 Tabla `budget_lines`

Crear tabla para líneas presupuestarias normalizadas.

Campos mínimos:

```text
id
budget_id
account_id
cost_center_id
business_unit_id
project_id
period_id
amount
description
created_at
updated_at
```

## 6.4 Campos

### `budget_id`

Obligatorio.

Referencia al presupuesto padre.

### `account_id`

Obligatorio.

Cuenta contable presupuestada.

Debe ser una cuenta válida para la compañía/libro contable.

Debe ser cuenta imputable/movible, no cuenta agrupadora, si el plan contable distingue entre ambas.

### `cost_center_id`

Obligatorio.

Centro de costo presupuestado.

Debe pertenecer a la compañía o ser válido para ella.

### `business_unit_id`

Opcional.

Unidad de negocio.

Debe validarse si existe en el modelo actual.

Si Cacao Accounting aún no tiene unidad de negocio como dimensión contable, el campo puede dejarse preparado pero no exponerse en UI hasta que exista la entidad.

### `project_id`

Opcional.

Proyecto asociado.

Debe validarse si existe en el modelo actual.

### `period_id`

Obligatorio.

Período contable dentro del año fiscal del presupuesto.

### `amount`

Obligatorio.

Monto presupuestado.

Debe permitir decimales.

Debe aceptar valores positivos y cero.

En primera versión, se recomienda permitir negativos solamente si el sistema contable ya los permite en otros documentos financieros y existe una justificación clara.

### `description`

Opcional.

Comentario de línea.

---

# 7. Restricciones de unicidad

Debe impedirse duplicar líneas dentro del mismo presupuesto para la misma combinación dimensional y período.

Restricción lógica:

```text
budget_id
account_id
cost_center_id
business_unit_id
project_id
period_id
```

## 7.1 Manejo de valores nulos

Como `business_unit_id` y `project_id` son opcionales, debe evitarse que la base de datos permita duplicados por el comportamiento de `NULL`.

La implementación debe normalizar esta validación desde el servicio de dominio aunque también exista restricción en base de datos.

Regla:

Dos líneas se consideran duplicadas si tienen el mismo:

```text
budget_id
account_id
cost_center_id
period_id
```

y además:

```text
business_unit_id ambos iguales o ambos vacíos
project_id ambos iguales o ambos vacíos
```

---

# 8. Servicios requeridos

## 8.1 `BudgetService`

Responsable de la lógica principal de presupuesto.

Métodos sugeridos:

```python
create_budget(data, user)
update_budget(budget_id, data, user)
delete_budget_line(line_id, user)
add_budget_line(budget_id, data, user)
update_budget_line(line_id, data, user)
approve_budget(budget_id, user)
close_budget(budget_id, user)
validate_budget(budget_id)
get_budget_totals(budget_id)
```

## 8.2 Reglas de `BudgetService`

### Crear presupuesto

Debe validar:

* Compañía existe.
* Libro contable existe.
* Libro contable pertenece a la compañía.
* Año fiscal existe.
* Moneda existe.
* Código no está duplicado para compañía/libro/año fiscal.
* Estado inicial siempre debe ser `draft`.

### Editar presupuesto

Solo permitido si:

```text
status = draft
```

No debe permitirse cambiar compañía, libro contable o año fiscal si el presupuesto ya tiene líneas.

### Agregar línea

Solo permitido si:

```text
budget.status = draft
```

Debe validar:

* Cuenta existe.
* Cuenta es válida para la compañía/libro.
* Centro de costo existe.
* Período pertenece al año fiscal del presupuesto.
* Unidad de negocio existe, si fue informada.
* Proyecto existe, si fue informado.
* No existe línea duplicada.
* Monto es numérico.

### Aprobar presupuesto

Solo permitido si:

```text
status = draft
```

Debe validar:

* El presupuesto tiene al menos una línea.
* Todas las líneas tienen período válido.
* Todas las líneas tienen cuenta válida.
* Todas las líneas tienen centro de costo válido.
* No existen duplicados.
* No existen montos nulos.
* El año fiscal tiene períodos contables configurados.
* Opcionalmente: todos los períodos del año fiscal tienen presupuesto para al menos alguna línea.

Al aprobar:

```text
status = approved
approved_by_id = current_user.id
approved_at = now()
```

### Cerrar presupuesto

Solo permitido si:

```text
status = approved
```

Al cerrar:

```text
status = closed
closed_by_id = current_user.id
closed_at = now()
```

---

# 9. Importación desde hoja de cálculo

## 9.1 Objetivo

Permitir que el usuario cargue presupuestos desde hoja de cálculo, ya que será el flujo más común.

Formatos deseados:

```text
.csv
.xls
.xlsx
.ods
```

La importación debe reutilizar el patrón de importación definido para Cacao Accounting cuando sea posible.

---

## 9.2 Ubicación de importación

La importación debe ejecutarse desde un presupuesto existente en estado borrador:

```text
Contabilidad > Presupuesto > Administrar presupuestos > Ver presupuesto > Importar líneas
```

No se debe importar a presupuestos aprobados ni cerrados.

---

## 9.3 Estructura de plantilla

La hoja debe estar en formato matriz.

Ejemplo:

```text
Cuenta | Centro de Costo | Unidad de Negocio | Proyecto | 2026-01 | 2026-02 | 2026-03 | ... | 2026-12 | Total
```

Ejemplo:

| Cuenta   | Centro de Costo | Unidad de Negocio | Proyecto | 2026-01 | 2026-02 | 2026-03 |   Total |
| -------- | --------------- | ----------------- | -------- | ------: | ------: | ------: | ------: |
| 6101-001 | ADMIN           |                   |          | 1000.00 | 1200.00 |  900.00 | 3100.00 |
| 6201-001 | VENTAS          | RETAIL            |          |  500.00 |  700.00 |  800.00 | 2000.00 |

## 9.4 Columnas requeridas

Obligatorias:

```text
Cuenta
Centro de Costo
```

Opcionales:

```text
Unidad de Negocio
Proyecto
Descripción
Total
```

Columnas dinámicas:

```text
Una columna por período contable del año fiscal
```

Ejemplo:

```text
2026-01
2026-02
2026-03
...
```

Las columnas de período deben coincidir con los períodos configurados del año fiscal, no con meses hardcodeados.

---

# 10. Servicio de importación

## 10.1 `BudgetImportService`

Métodos sugeridos:

```python
get_template_columns(budget_id)
parse_file(file)
validate_import(budget_id, parsed_rows)
insert_lines(budget_id, validated_rows, user)
```

## 10.2 Validación antes de insertar

La importación debe tener dos pasos obligatorios:

1. **Validar**
2. **Insertar líneas**

La UI no debe mostrar el botón **Insertar líneas** hasta que la validación sea exitosa.

Estado inicial del modal:

```text
Cancelar
Validar
```

Después de validación exitosa:

```text
Cancelar
Insertar líneas
```

---

# 11. Reglas de validación de importación

Antes de insertar líneas, validar:

## 11.1 Archivo

* El archivo existe.
* El formato está soportado.
* El archivo no está vacío.
* La hoja contiene encabezados.
* No hay columnas duplicadas.
* No hay columnas de período desconocidas.

## 11.2 Encabezados

Validar que existan:

```text
Cuenta
Centro de Costo
```

Validar que las columnas de períodos correspondan al año fiscal del presupuesto.

No se deben aceptar columnas de períodos fuera del año fiscal.

## 11.3 Filas

Por cada fila validar:

* Cuenta informada.
* Cuenta existe.
* Cuenta pertenece al plan contable aplicable.
* Cuenta permite movimientos.
* Centro de costo informado.
* Centro de costo existe.
* Unidad de negocio existe, si fue informada.
* Proyecto existe, si fue informado.
* Cada monto de período es numérico o vacío.
* Los vacíos se interpretan como cero o se omiten, según decisión técnica.
* Recomendación: vacío = cero y no generar línea si el monto queda en cero.
* Si existe columna Total, validar que coincide con la suma de períodos.
* No hay combinaciones duplicadas dentro del archivo.
* No hay combinaciones duplicadas contra líneas existentes del presupuesto, salvo que se implemente modo reemplazo.

## 11.4 Errores

Los errores deben reportarse con:

```text
número de fila
columna
valor recibido
mensaje claro
```

Ejemplo:

```text
Fila 8, columna Cuenta: la cuenta 6101-999 no existe.
Fila 12, columna 2026-03: el valor "ABC" no es numérico.
Fila 15: combinación duplicada para Cuenta 6101-001, Centro ADMIN, Proyecto vacío.
```

---

# 12. Comportamiento de inserción

La inserción debe ser:

* Transaccional.
* Atómica.
* Segura.
* Sin inserciones parciales si ocurre un error.

Si una fila tiene montos para varios períodos, debe crear una línea normalizada por cada período con monto diferente de cero.

Ejemplo de entrada:

```text
Cuenta: 6101-001
Centro de Costo: ADMIN
2026-01: 1000
2026-02: 1200
2026-03: 900
```

Debe generar:

```text
budget_id, account_id, cost_center_id, period_id=2026-01, amount=1000
budget_id, account_id, cost_center_id, period_id=2026-02, amount=1200
budget_id, account_id, cost_center_id, period_id=2026-03, amount=900
```

---

# 13. Política append-only o reemplazo

Para esta funcionalidad se recomienda que la importación sea **append-only por defecto**, consistente con el patrón discutido para importación de líneas.

Regla inicial:

* La importación agrega líneas.
* No elimina líneas existentes.
* No reemplaza líneas manuales.
* Si el archivo contiene una combinación ya existente, debe generar error de duplicado.

Esto evita que el usuario pierda líneas ingresadas manualmente.

Una opción de reemplazo puede agregarse después, pero no debe formar parte del alcance inicial salvo que se implemente con confirmación explícita y auditoría.

---

# 14. Interfaz de usuario

## 14.1 Listado de presupuestos

Ruta sugerida:

```text
/contabilidad/presupuestos
```

Columnas:

```text
Código
Nombre
Compañía
Libro contable
Año fiscal
Moneda
Estado
Creado por
Fecha creación
Aprobado por
Fecha aprobación
Acciones
```

Acciones por estado:

### Borrador

```text
Ver
Editar
Importar
Aprobar
Eliminar, opcional
```

### Aprobado

```text
Ver
Cerrar
Real versus Presupuesto
```

### Cerrado

```text
Ver
Real versus Presupuesto
```

---

## 14.2 Formulario de presupuesto

Ruta sugerida:

```text
/contabilidad/presupuestos/nuevo
/contabilidad/presupuestos/<id>/editar
```

Campos:

```text
Compañía
Libro contable
Año fiscal
Código
Nombre
Descripción
Moneda
```

Reglas UX:

* Al seleccionar compañía, filtrar libros contables disponibles.
* Al seleccionar año fiscal, cargar períodos asociados.
* El estado no debe ser editable manualmente.
* El presupuesto siempre inicia como borrador.

---

## 14.3 Vista de detalle del presupuesto

Ruta sugerida:

```text
/contabilidad/presupuestos/<id>
```

Debe mostrar:

1. Encabezado.
2. Estado.
3. Auditoría.
4. Totales por período.
5. Líneas presupuestarias.
6. Acciones disponibles según estado.

Acciones en borrador:

```text
Editar encabezado
Agregar línea
Editar línea
Eliminar línea
Importar líneas
Validar
Aprobar
```

Acciones en aprobado:

```text
Cerrar
Ver reporte Real versus Presupuesto
```

Acciones en cerrado:

```text
Ver reporte Real versus Presupuesto
```

---

## 14.4 Edición de líneas manuales

La UI debe permitir agregar líneas manualmente.

Campos:

```text
Cuenta contable
Centro de costo
Unidad de negocio, opcional
Proyecto, opcional
Período contable
Monto
Descripción
```

Puede implementarse inicialmente como formulario de línea individual.

Posteriormente puede mejorarse a una matriz editable:

```text
Cuenta | Centro de Costo | Unidad de Negocio | Proyecto | P01 | P02 | P03 | ... | Total
```

Internamente siempre debe persistirse normalizado por período.

---

# 15. Reporte Real versus Presupuesto

## 15.1 Objetivo

Crear un reporte que compare el presupuesto seleccionado contra la ejecución real registrada en contabilidad.

Nombre del reporte:

```text
Real versus Presupuesto
```

Ubicación:

```text
Contabilidad > Presupuesto > Real versus Presupuesto
```

---

## 15.2 Filtros

Filtros obligatorios:

```text
Compañía
Libro contable
Año fiscal
Presupuesto
Rango de períodos
```

Filtros opcionales:

```text
Cuenta contable desde
Cuenta contable hasta
Centro de costo
Unidad de negocio
Proyecto
Mostrar solo cuentas con variación
Mostrar solo líneas con presupuesto
Mostrar solo líneas con real
```

Reglas:

* El filtro de presupuesto debe mostrar presupuestos de la compañía, libro y año fiscal seleccionados.
* Por defecto debe mostrar presupuestos aprobados.
* Puede permitir incluir cerrados.
* No debe incluir borradores por defecto.

---

## 15.3 Columnas mínimas

El reporte debe mostrar:

```text
Cuenta contable
Nombre de cuenta
Centro de costo
Unidad de negocio
Proyecto
Período
Presupuesto
Real
Variación
Variación %
```

Columnas recomendadas adicionales:

```text
Presupuesto acumulado
Real acumulado
Variación acumulada
Variación acumulada %
```

---

## 15.4 Fórmulas

```text
variacion = real - presupuesto
```

```text
variacion_porcentaje = variacion / presupuesto
```

Cuando presupuesto sea cero:

```text
Si real = 0:
    variacion_porcentaje = 0

Si real != 0:
    variacion_porcentaje = N/A
```

---

# 16. Cálculo del real

El monto real debe obtenerse exclusivamente desde la contabilidad posteada.

Fuente de verdad:

```text
líneas contables contabilizadas / libro mayor
```

No debe calcularse desde documentos fuente no contabilizados.

## 16.1 Filtros para el real

Debe considerar:

```text
company_id
ledger_id
period_id
account_id
cost_center_id
business_unit_id, si aplica
project_id, si aplica
```

Debe excluir:

```text
documentos en borrador
documentos anulados
documentos reversados sin efecto vigente
líneas no posteadas
```

## 16.2 Signo contable

Debe definirse una normalización clara.

Recomendación:

* El presupuesto se captura como monto positivo.
* El reporte normaliza el real según la naturaleza de la cuenta.
* Para gastos, el débito neto debe presentarse positivo.
* Para ingresos, el crédito neto debe presentarse positivo.

Ejemplo conceptual:

```text
Gasto real = débitos - créditos
Ingreso real = créditos - débitos
Activo real = débitos - créditos
Pasivo real = créditos - débitos
Patrimonio real = créditos - débitos
```

Esto debe ajustarse a la lógica de naturaleza de cuenta existente en Cacao Accounting.

---

# 17. Servicio de reporte

## 17.1 `BudgetReportService`

Métodos sugeridos:

```python
get_real_vs_budget(filters)
get_budget_amounts(budget_id, filters)
get_actual_amounts(company_id, ledger_id, filters)
merge_budget_and_actual(budget_rows, actual_rows)
calculate_variances(rows)
```

## 17.2 Comportamiento

El reporte debe hacer un cruce entre:

```text
presupuesto por dimensiones
real por dimensiones
```

Debe incluir:

* Líneas con presupuesto aunque no tengan real.
* Líneas con real aunque no tengan presupuesto, si el usuario activa la opción correspondiente.
* Totales por período.
* Totales acumulados.

---

# 18. Permisos requeridos

Agregar permisos específicos dentro del sistema de autorización.

```text
budget.view
budget.create
budget.edit
budget.delete
budget.import
budget.approve
budget.close
budget.report
```

## 18.1 Reglas por permiso

### `budget.view`

Permite ver listado y detalle.

### `budget.create`

Permite crear encabezados.

### `budget.edit`

Permite editar presupuestos en borrador.

### `budget.delete`

Permite eliminar presupuestos en borrador, si no tienen aprobaciones ni uso posterior.

### `budget.import`

Permite importar líneas.

### `budget.approve`

Permite aprobar presupuestos.

### `budget.close`

Permite cerrar presupuestos.

### `budget.report`

Permite ejecutar el reporte Real versus Presupuesto.

---

# 19. Validaciones generales

## 19.1 Presupuesto

Debe impedirse:

* Crear presupuesto sin compañía.
* Crear presupuesto sin libro contable.
* Crear presupuesto sin año fiscal.
* Crear presupuesto sin código.
* Crear presupuesto sin nombre.
* Crear código duplicado para la misma compañía/libro/año fiscal.
* Aprobar presupuesto sin líneas.
* Editar presupuesto aprobado.
* Editar presupuesto cerrado.
* Importar líneas a presupuesto aprobado.
* Importar líneas a presupuesto cerrado.
* Cerrar presupuesto en borrador.

## 19.2 Líneas

Debe impedirse:

* Línea sin cuenta.
* Línea sin centro de costo.
* Línea sin período.
* Línea con período fuera del año fiscal.
* Línea duplicada por combinación dimensional.
* Línea con cuenta inválida.
* Línea con cuenta agrupadora/no imputable.
* Línea con centro de costo inválido.
* Línea con monto no numérico.

---

# 20. Auditoría

Debe registrarse auditoría mínima para eventos de estado:

## 20.1 Creación

```text
created_by_id
created_at
```

## 20.2 Aprobación

```text
approved_by_id
approved_at
```

## 20.3 Cierre

```text
closed_by_id
closed_at
```

## 20.4 Importación

Se recomienda crear una tabla opcional de historial de importaciones:

```text
budget_imports
```

Campos sugeridos:

```text
id
budget_id
filename
status
rows_read
rows_inserted
errors_count
created_by_id
created_at
```

Estados sugeridos:

```text
validated
inserted
failed
```

Esto no es estrictamente obligatorio para la primera versión, pero es recomendable.

---

# 21. Estructura técnica sugerida

Asumiendo que el módulo existente es `contabilidad`.

## 21.1 Archivos sugeridos

```text
cacao_accounting/contabilidad/models/budget.py
cacao_accounting/contabilidad/forms/budget_forms.py
cacao_accounting/contabilidad/services/budget_service.py
cacao_accounting/contabilidad/services/budget_import_service.py
cacao_accounting/contabilidad/services/budget_report_service.py
cacao_accounting/contabilidad/routes/budget_routes.py
cacao_accounting/contabilidad/templates/contabilidad/presupuestos/
```

Si el proyecto usa archivos monolíticos:

```text
cacao_accounting/contabilidad/models.py
cacao_accounting/contabilidad/forms.py
cacao_accounting/contabilidad/routes.py
cacao_accounting/contabilidad/services/budget_service.py
cacao_accounting/contabilidad/services/budget_import_service.py
cacao_accounting/contabilidad/services/budget_report_service.py
```

---

# 22. Templates requeridos

Crear templates bajo:

```text
templates/contabilidad/presupuestos/
```

Templates mínimos:

```text
list.html
form.html
detail.html
line_form.html
import.html
real_vs_budget.html
```

## 22.1 `list.html`

Listado de presupuestos.

## 22.2 `form.html`

Creación y edición del encabezado.

## 22.3 `detail.html`

Detalle del presupuesto y sus líneas.

## 22.4 `line_form.html`

Alta y edición de línea presupuestaria.

## 22.5 `import.html`

Carga y validación de archivo.

## 22.6 `real_vs_budget.html`

Filtros y resultado del reporte.

---

# 23. UX esperada

Debe mantenerse consistencia visual con el UX actual del módulo de Contabilidad.

Recomendaciones:

* Usar los mismos estilos de formularios que comprobante contable.
* Usar Smart Select para:

  * compañía,
  * libro contable,
  * año fiscal,
  * cuenta contable,
  * centro de costo,
  * unidad de negocio,
  * proyecto,
  * presupuesto.
* Mostrar badges de estado:

  * Borrador,
  * Aprobado,
  * Cerrado.
* Mostrar acciones según estado y permisos.
* Evitar botones inválidos para el estado actual.

---

# 24. Integración con importación común

Si ya existe o se está implementando un servicio común de importación de líneas, Presupuesto debe integrarse con ese patrón.

El backend debe exponer la definición de columnas esperadas.

Ejemplo conceptual:

```python
BudgetImportService.get_template_columns(budget_id)
```

Debe retornar:

```json
[
  {"name": "Cuenta", "required": true, "type": "string"},
  {"name": "Centro de Costo", "required": true, "type": "string"},
  {"name": "Unidad de Negocio", "required": false, "type": "string"},
  {"name": "Proyecto", "required": false, "type": "string"},
  {"name": "2026-01", "required": false, "type": "decimal"},
  {"name": "2026-02", "required": false, "type": "decimal"}
]
```

El frontend solo debe parsear y presentar el archivo.

El backend debe ser responsable de:

* Validar columnas.
* Resolver IDs.
* Validar relaciones.
* Detectar duplicados.
* Insertar líneas.

---

# 25. Migraciones

Crear migración para:

```text
budgets
budget_lines
budget_imports, opcional
```

## 25.1 Índices recomendados

Para `budgets`:

```text
company_id
ledger_id
fiscal_year_id
status
company_id + ledger_id + fiscal_year_id + budget_code
```

Para `budget_lines`:

```text
budget_id
account_id
cost_center_id
period_id
business_unit_id
project_id
```

Índice compuesto recomendado:

```text
budget_id + account_id + cost_center_id + period_id
```

---

# 26. Casos de prueba requeridos

## 26.1 Creación de presupuesto

Debe probarse que:

* Se puede crear presupuesto válido.
* El estado inicial es borrador.
* No se puede crear sin compañía.
* No se puede crear sin libro contable.
* No se puede crear sin año fiscal.
* No se puede duplicar código en la misma compañía/libro/año fiscal.
* Sí se puede usar el mismo código en otra compañía, si aplica.
* Sí se puede crear más de un presupuesto para el mismo año fiscal con códigos distintos.

## 26.2 Líneas presupuestarias

Debe probarse que:

* Se puede crear línea válida.
* No se puede crear línea sin cuenta.
* No se puede crear línea sin centro de costo.
* No se puede crear línea sin período.
* No se puede usar período fuera del año fiscal.
* No se puede duplicar combinación dimensional.
* No se puede usar cuenta inválida.
* No se puede usar cuenta agrupadora si el sistema distingue cuentas agrupadoras.
* No se puede editar línea si el presupuesto está aprobado.
* No se puede editar línea si el presupuesto está cerrado.

## 26.3 Estados

Debe probarse que:

* Un presupuesto borrador puede aprobarse si tiene líneas válidas.
* Un presupuesto sin líneas no puede aprobarse.
* Un presupuesto aprobado no puede editarse.
* Un presupuesto aprobado puede cerrarse.
* Un presupuesto cerrado no puede editarse.
* Un presupuesto cerrado no puede aprobarse nuevamente.
* Un presupuesto borrador no puede cerrarse directamente.

## 26.4 Importación

Debe probarse que:

* Se puede validar archivo válido.
* Se puede insertar archivo válido después de validación.
* No se muestran acciones de inserción antes de validar.
* No se inserta si hay errores.
* No se insertan líneas parcialmente.
* Se detecta cuenta inexistente.
* Se detecta centro de costo inexistente.
* Se detecta período inválido.
* Se detecta monto no numérico.
* Se detecta total inconsistente.
* Se detectan duplicados dentro del archivo.
* Se detectan duplicados contra líneas existentes.
* No se permite importar a presupuesto aprobado.
* No se permite importar a presupuesto cerrado.

## 26.5 Reporte Real versus Presupuesto

Debe probarse que:

* El reporte carga filtros.
* El reporte permite seleccionar presupuesto aprobado.
* El reporte compara presupuesto contra real.
* El reporte muestra líneas con presupuesto y sin real.
* El reporte calcula variación.
* El reporte calcula variación porcentual.
* El reporte maneja presupuesto cero.
* El reporte excluye documentos anulados.
* El reporte excluye documentos no contabilizados.
* El reporte respeta compañía.
* El reporte respeta libro contable.
* El reporte respeta período.
* El reporte respeta cuenta.
* El reporte respeta centro de costo.
* El reporte respeta proyecto si aplica.
* El reporte respeta unidad de negocio si aplica.

---

# 27. Criterios de aceptación finales

La implementación se considera completa cuando:

1. Existe el submenú **Contabilidad > Presupuesto**.
2. Existe la pantalla **Administrar presupuestos**.
3. Se pueden crear presupuestos por compañía, libro contable y año fiscal.
4. Se pueden crear múltiples presupuestos para el mismo año fiscal.
5. El presupuesto inicia como borrador.
6. El presupuesto puede tener líneas por cuenta, centro de costo y período.
7. Unidad de negocio y proyecto son opcionales.
8. El sistema valida duplicados de líneas.
9. El sistema permite edición solo en estado borrador.
10. El sistema permite aprobar presupuestos válidos.
11. El sistema bloquea edición de presupuestos aprobados.
12. El sistema permite cerrar presupuestos aprobados.
13. El sistema bloquea edición de presupuestos cerrados.
14. El sistema permite importar presupuesto desde hoja de cálculo.
15. La importación valida antes de insertar.
16. La importación no elimina líneas existentes.
17. La importación no hace inserciones parciales en caso de error.
18. Existe el reporte **Real versus Presupuesto**.
19. El reporte compara contra líneas contables contabilizadas.
20. El reporte excluye documentos anulados o no posteados.
21. El reporte muestra presupuesto, real, variación y variación porcentual.
22. Existen pruebas automatizadas para servicios principales, importación y reporte.

---

# 28. Decisiones explícitas de esta versión

Para evitar ambigüedad, esta implementación debe asumir:

```text
Presupuesto es submódulo de Contabilidad.
No es módulo top-level.
```

```text
Puede haber múltiples presupuestos por compañía, libro contable y año fiscal.
```

```text
El presupuesto se guarda normalizado por período contable.
```

```text
La carga por hoja de cálculo usa formato matriz, pero se persiste como líneas normalizadas.
```

```text
La importación es append-only.
```

```text
El real se obtiene únicamente desde contabilidad posteada.
```

```text
El presupuesto aprobado no se edita directamente.
```

```text
El presupuesto cerrado es solo consulta histórica.
```

```text
El reporte Real versus Presupuesto pertenece al submódulo de Presupuesto dentro de Contabilidad.
```

