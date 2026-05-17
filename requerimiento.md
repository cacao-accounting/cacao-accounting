# Requerimiento Funcional y Técnico

# Exchange Revaluation (Revalorización Cambiaria NIIF Multiledger)

## Objetivo

Implementar un proceso completo de **Revalorización Cambiaria** conforme a **NIC 21 / NIIF**, integrado al motor contable multiledger de Cacao Accounting.

El proceso debe recalcular el valor contable de partidas monetarias abiertas usando tasas de cierre y reconocer diferencias cambiarias no realizadas en resultados.

La implementación debe:

* cumplir criterios NIIF,
* soportar multiledger,
* integrarse a AR/AP/Bancos,
* operar a nivel documental,
* ser totalmente auditable,
* ser idempotente,
* soportar múltiples ejecuciones por período,
* permitir reversión/anulación,
* integrarse al cierre mensual,
* y funcionar también de forma independiente.

---

# Base NIIF

La implementación debe alinearse con NIC 21:

* Las partidas monetarias en moneda extranjera deben convertirse usando la tasa de cierre.
* Las diferencias cambiarias deben reconocerse en resultados.
* Solo deben revalorizarse partidas monetarias.
* Solo deben revalorizarse saldos abiertos o pendientes.
* La revalorización debe impactar el valor contable vigente del saldo pendiente.

---

# Alcance funcional

## Debe revalorizar

### Accounts Receivable (AR)

* Facturas abiertas
* Notas de débito abiertas
* Notas de crédito parcialmente aplicadas
* Anticipos abiertos
* Saldos pendientes parciales

---

## Accounts Payable (AP)

* Facturas proveedor abiertas
* Notas de débito proveedor
* Notas de crédito parcialmente aplicadas
* Anticipos abiertos
* Obligaciones pendientes

---

## Bancos

* Saldos bancarios monetarios
* Cuentas bancarias en moneda extranjera

---

## Otras cuentas monetarias

Solo si:

```text id="3v6g6o"
monetary_account = true
exchange_revaluation_enabled = true
```

---

# No debe revalorizar

* Inventarios
* Activos fijos
* Gastos
* Ingresos
* Patrimonio
* Impuestos
* Cuentas no monetarias
* Documentos totalmente cerrados
* Documentos totalmente conciliados
* Moneda original del documento

---

# Arquitectura multiledger

## Regla principal

La moneda original del documento NO se revaloriza.

Solo se revalorizan ledgers cuya moneda sea distinta a la moneda origen.

---

# Ejemplo

Ledgers activos:

```text id="62b6kq"
NIO
USD
EUR
```

Factura registrada originalmente en USD.

Resultado:

| Ledger | Revaloriza |
| ------ | ---------- |
| USD    | No         |
| NIO    | Sí         |
| EUR    | Sí         |

---

# Integración subledger obligatoria

La revalorización debe operar a nivel documental.

NO se permiten ajustes globales resumidos por cuenta.

---

# Granularidad obligatoria

Cada documento abierto debe generar su propia línea de revalorización.

Ejemplos:

* Factura
* Nota débito
* Nota crédito
* Anticipo
* Saldo bancario identificado

---

# Impacto obligatorio en AR/AP

Los movimientos de revalorización deben impactar directamente:

* saldo abierto documental,
* subledger,
* aging,
* open items,
* estado de cuenta.

---

# Resultado esperado

Los reportes de:

* AR Aging
* AP Aging
* Open Items
* Estado de cuenta
* Balance multiledger

deben mostrar automáticamente valores revaluados.

---

# Configuración requerida

## Configuración global compañía

Agregar:

```text id="1jk7pz"
company.exchange_gain_account_id
company.exchange_loss_account_id
```

---

# Validaciones obligatorias

El proceso debe fallar si:

* no existe cuenta ganancia cambiaria,
* no existe cuenta pérdida cambiaria,
* falta tasa de cierre,
* período cerrado,
* ledger inactivo,
* moneda inválida,
* configuración inconsistente,
* cuenta monetaria mal configurada.

---

# Tipos de comprobante

Crear nuevo tipo:

```text id="hzm4p2"
exchange-revaluation
```

Debe diferenciarse de:

* journal-entry
* recurring-entry
* closing-entry

---

# Menú

Agregar:

```text id="o7ifm2"
Contabilidad → Revalorización cambiaria
```

---

# Pantalla principal

Debe listar:

| Campo                 |
| --------------------- |
| Número                |
| Compañía              |
| Mes                   |
| Año                   |
| Fecha                 |
| Estado                |
| Usuario               |
| Total ganancia        |
| Total pérdida         |
| Documentos procesados |
| Documentos afectados  |

---

# Estados

```text id="jlwm4r"
posted
voided
completed_no_changes
```

---

# Nueva revalorización

Formulario mínimo:

```text id="s1mxp5"
- Compañía
- Mes
- Año
```

---

# Flujo de ejecución

## Paso 1

Usuario selecciona:

* compañía
* mes
* año

---

## Paso 2

Sistema:

* identifica ledgers activos,
* identifica monedas destino,
* obtiene tasas de cierre,
* obtiene documentos abiertos,
* obtiene saldos pendientes,
* valida configuración.

---

## Paso 3

Si existen errores:

* NO contabilizar,
* mostrar lista completa de errores.

---

## Paso 4

Si existen diferencias:

* generar comprobante,
* contabilizar automáticamente,
* estado `posted`.

---

## Paso 5

Si NO existen diferencias:

* guardar ejecución,
* NO generar comprobante,
* estado `completed_no_changes`.

Mensaje:

```text id="a8iv6f"
La revalorización fue ejecutada correctamente.
No se generaron diferencias cambiarias.
```

---

# UX

Debe reutilizar UX del comprobante contable.

Referencias:

```text id="smx1x0"
journal.html
journal_nuevo.html
```

---

# Restricciones UX

Usuario NO puede:

* editar líneas,
* cambiar cuentas,
* cambiar montos,
* cambiar tasas,
* agregar líneas,
* eliminar líneas.

---

# Información obligatoria visible

* documento origen,
* tercero,
* moneda origen,
* ledger destino,
* tasa aplicada,
* saldo original,
* saldo revaluado,
* diferencia,
* fecha ejecución,
* estado.

---

# Ejecuciones múltiples por período

El sistema debe permitir múltiples ejecuciones dentro del mismo período.

Ejemplo:

```text id="59mf6j"
Mayo 2026
- Run #1
- Run #2
- Run #3
```

---

# Regla de consistencia

Cada ejecución debe ser independiente y auditable.

Cada ejecución debe guardar:

* snapshot tasas,
* snapshot saldos,
* snapshot diferencias,
* detalle documental procesado.

---

# Idempotencia

El proceso debe ser idempotente.

---

# Regla técnica

Cada nueva ejecución debe calcular diferencias contra el saldo contable ACTUAL.

Incluyendo revalorizaciones previas activas.

---

# Fórmula principal

\text{valor revaluado} = \text{saldo pendiente moneda origen} \times \text{tasa cierre}

---

# Diferencia incremental

\text{diferencia nueva} = \text{valor revaluado actual} - \text{saldo ledger actual acumulado}

---

# Reglas contables

## Activos monetarios

Si aumenta:

```text id="rzr56l"
Dr Cuenta monetaria
Cr Ganancia cambiaria
```

Si disminuye:

```text id="6y8axg"
Dr Pérdida cambiaria
Cr Cuenta monetaria
```

---

## Pasivos monetarios

Aplicar lógica inversa según naturaleza.

---

# Contabilización obligatoria a nivel documental

Cada documento debe generar líneas independientes.

Ejemplo:

Factura:

```text id="31wfru"
INV-1001
USD 1,000
```

Debe generar:

```text id="ct2b0y"
Dr AR Customer ABC
Cr Ganancia cambiaria
```

asociado explícitamente a:

```text id="9k5m2k"
source_document = INV-1001
```

---

# Reversión / anulación

La revalorización NO se edita.

Debe anularse completamente.

---

# Anulación debe

* generar asiento reverso,
* revertir impacto documental,
* revertir saldos AR/AP,
* recalcular aging,
* mantener trazabilidad,
* no eliminar registros históricos.

---

# Estados posteriores

```text id="x6b09h"
posted
voided
completed_no_changes
```

---

# Modelo de datos

## exchange_revaluation_run

Campos mínimos:

```text id="5xjlwm"
id
company_id
year
month
status
generated_journal
journal_id
reversal_journal_id
created_by
created_at
voided_by
voided_at
void_reason
processed_documents_count
affected_documents_count
total_gain
total_loss
```

---

## exchange_revaluation_line

Campos mínimos:

```text id="hvcx1l"
id
run_id
source_document_type
source_document_id
partner_id
account_id
ledger_id
original_currency_id
ledger_currency_id
open_amount_original
previous_ledger_balance
closing_rate
revalued_balance
exchange_difference
journal_line_id
```

---

# Journal lines

Agregar:

```text id="mkk57j"
exchange_revaluation_run_id
```

Esto permitirá:

* auditoría,
* trazabilidad,
* reversión,
* reconstrucción histórica.

---

# Servicio interno

Crear:

```text id="6vxlm5"
ExchangeRevaluationService
```

---

# Responsabilidades del servicio

* validar configuración,
* obtener tasas,
* obtener documentos abiertos,
* calcular diferencias,
* generar líneas documentales,
* generar comprobante,
* contabilizar,
* revertir,
* garantizar idempotencia,
* recalcular incrementalmente.

---

# Integración cierre mensual

Orden obligatorio:

```text id="j29m09"
1. Validar período
2. Aplicar recurrentes
3. Ejecutar revalorización
4. Ajustes de cierre
5. Validaciones
6. Bloqueo período
```

---

# Integración independiente

Debe poder ejecutarse manualmente desde menú contable.

Ambos flujos deben usar exactamente el mismo servicio.

---

# Corrección de errores

Si la revalorización es incorrecta:

```text id="f9pv6l"
1. Anular revalorización
2. Corregir documento fuente
3. Ejecutar nuevamente
```

Nunca editar comprobante manualmente.

---

# Casos de prueba mínimos

## Caso 1

Factura USD abierta.

Ledgers:

* USD
* NIO
* EUR

Resultado:

* USD no revaloriza
* NIO sí
* EUR sí

---

## Caso 2

Factura parcialmente pagada.

Resultado:

* solo saldo pendiente revaloriza.

---

## Caso 3

Factura totalmente pagada.

Resultado:

* no revaloriza.

---

## Caso 4

Cuenta bancaria USD.

Resultado:

* revaloriza ledgers destino.

---

## Caso 5

Cuenta no monetaria.

Resultado:

* no revaloriza.

---

## Caso 6

Falta tasa cierre.

Resultado:

* error controlado.

---

## Caso 7

Falta cuenta ganancia/pérdida.

Resultado:

* error controlado.

---

## Caso 8

Múltiples ejecuciones mismo período.

Resultado:

* cálculo incremental correcto.

---

## Caso 9

Revalorización sin diferencias.

Resultado:

* guarda ejecución sin comprobante.

---

## Caso 10

Anulación.

Resultado:

* reverso correcto y restauración documental.

---

## Caso 11

Nueva ejecución posterior a anulación.

Resultado:

* recalcula correctamente.

---

## Caso 12

Aging AR/AP.

Resultado:

* muestra saldo revaluado actualizado.

---

# Criterio final de aceptación

La implementación estará completa cuando el sistema pueda ejecutar revalorizaciones cambiarias NIIF-compatible sobre partidas monetarias abiertas, operando a nivel documental, soportando multiledger, excluyendo moneda origen, integrándose a AR/AP/Bancos, permitiendo múltiples ejecuciones por período, calculando diferencias incrementalmente, generando comprobantes automáticos tipo `exchange-revaluation`, soportando reversión completa y reflejando correctamente saldos revaluados en subledgers y reportes contables.

Ajustes al requerimiento
Revalorizaciones múltiples por período
Cambio de regla

Eliminar restricción:

UNA revalorización activa por compañía + período + ledger
Nueva regla

El sistema debe permitir ejecutar múltiples revalorizaciones dentro del mismo período.

Ejemplo:

Mayo 2026
- Revalorización #1
- Revalorización #2
- Revalorización #3

Esto es necesario porque:

pueden corregirse documentos,
pueden registrarse pagos tardíos,
pueden cambiar tasas,
pueden corregirse conciliaciones,
pueden ingresarse documentos retroactivos.
Reglas de consistencia

Cada ejecución debe ser independiente y auditada.

Cada ejecución debe:

generar su propio comprobante,
guardar snapshot de tasas,
guardar snapshot de saldos abiertos,
guardar detalle documental procesado.
Cálculo incremental obligatorio

La nueva ejecución NO debe duplicar diferencias ya contabilizadas.

La revalorización debe calcularse contra el valor contable ACTUAL, incluyendo revalorizaciones previas activas.

Es decir:

diferencia nueva=valor revaluado actual−saldo ledger actual acumulado

Esto convierte el proceso en acumulativo y consistente.

Revalorizaciones sin afectación contable
Nueva regla

Si el proceso no genera diferencias:

igualmente debe registrarse la ejecución,
igualmente debe quedar auditada,
NO debe generarse comprobante contable,
debe notificarse al usuario:
La revalorización fue ejecutada correctamente.
No se generaron diferencias cambiarias.
Modelo actualizado
exchange_revaluation_run

Agregar:

generated_journal = true/false
processed_documents_count
affected_documents_count
Confirmación funcional AR/AP

Sí.

Con este enfoque los reportes de:

Accounts Receivable
Accounts Payable
Aging
Open Items
Estado de cuenta

mostrarán automáticamente los saldos revaluados SI:

Condición obligatoria

La revalorización genera movimientos contables directamente sobre:

cuenta contable AR/AP,
subledger del documento,
saldo abierto del documento.
Requisito CRÍTICO

La revalorización NO debe generar un ajuste global resumido por cuenta.

Debe generar líneas a nivel documental.

Granularidad obligatoria

Cada documento monetario abierto genera su propia línea de revalorización.

Ejemplos:

Factura
Nota de débito
Nota de crédito
Anticipo abierto
Saldo bancario identificable
Ejemplo

Factura:

INV-1001
USD 1,000

Debe generar:

Dr AR Customer ABC
Cr Ganancia cambiaria

referenciando explícitamente:

source_document = INV-1001
Impacto esperado

Gracias a esto:

AR/AP Aging

Mostrará:

saldo original,
saldo revaluado,
diferencia cambiaria acumulada.
Estado de cuenta cliente/proveedor

Mostrará movimientos de revalorización asociados al documento.

Conciliación

La diferencia cambiaria queda asociada documentalmente.

Requisito técnico importante

Las líneas de revalorización deben mantener:

source_document_type
source_document_id
partner_id
currency_id
ledger_id
Requisito adicional altamente recomendado

Agregar:

exchange_revaluation_run_id

en journal lines.

Esto permitirá:

trazabilidad,
reversión,
auditoría,
reconstrucción histórica.
Requisito contable importante

La reversión/anulación debe revertir también el impacto documental.

Es decir:

AR/AP abiertos deben regresar a su saldo previo,
aging debe recalcularse,
balances deben reflejar reversión.