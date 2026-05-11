Requerimiento Técnico: Comprobantes Recurrentes y Asistente de Cierre Mensual

1. Objetivo

Implementar una funcionalidad de Comprobantes Recurrentes que permita definir una afectación contable completa una sola vez y aplicarla automáticamente por periodo contable, sin duplicaciones, como parte del proceso de Cierre Mensual.

El comprobante recurrente no debe afectar directamente el ledger al aprobarse. Su aprobación crea una plantilla contable activa que podrá ser aplicada posteriormente desde el Asistente de Cierre Mensual.

1. Concepto General

Un Comprobante Recurrente representa una plantilla contable aprobada para generar comprobantes contables reales en periodos futuros.

Ejemplos:

Amortización mensual de seguros pagados por anticipado.
Depreciación mensual.
Devengo mensual de gastos.
Reclasificaciones periódicas.
Provisiones recurrentes.
Distribuciones contables mensuales.
3. Estados del Comprobante Recurrente

El comprobante recurrente debe manejar los siguientes estados:

3.1 Borrador

Estado inicial.

Características:

Editable.
No puede aplicarse.
No afecta ledger.
Puede eliminarse si no tiene historial de aplicación.
3.2 Aprobado

Estado activo.

Características:

No debe ser editable en sus líneas contables críticas.
Puede ser aplicado por periodo desde el Asistente de Cierre Mensual.
No afecta ledger al momento de aprobación.
Representa una plantilla válida para generación de comprobantes.
3.3 Cancelado

Estado inactivo por decisión del usuario.

Características:

No puede aplicarse a nuevos periodos.
Conserva historial de aplicaciones anteriores.
No elimina comprobantes ya generados.
Debe requerir motivo de cancelación.
3.4 Completado

Estado final automático o manual controlado.

Características:

Se alcanza cuando ya fue aplicado el comprobante correspondiente al último periodo definido.
No puede aplicarse nuevamente.
Conserva historial completo.
No debe permitir nuevas aplicaciones.
4. Campos Principales del Comprobante Recurrente
4.1 Header

Campos mínimos:

ID.
Código o número interno.
Compañía.
Libro contable / ledger.
Nombre del comprobante recurrente.
Descripción.
Fecha de inicio.
Fecha de fin.
Periodicidad: por ahora mensual.
Estado.
Moneda.
Tipo de comprobante.
Diario contable, si aplica.
Referencia.
Creado por.
Fecha de creación.
Aprobado por.
Fecha de aprobación.
Cancelado por.
Fecha de cancelación.
Motivo de cancelación.
Fecha de último periodo aplicado.
Próximo periodo sugerido.
Indicación de si está completamente aplicado.
4.2 Líneas contables

Cada comprobante recurrente debe contener una afectación contable completa:

Cuenta contable.
Débito.
Crédito.
Descripción de línea.
Centro de costo.
Unidad de negocio.
Proyecto.
Dimensiones analíticas adicionales.
Tercero / proveedor / cliente, si aplica.
Moneda.
Tipo de cambio, si aplica.
Referencia documental, si aplica.

Regla crítica:

La plantilla debe estar balanceada antes de poder aprobarse.

1. Reglas Contables
5.1 Aprobación no afecta ledger

Al aprobar un comprobante recurrente:

No se crea movimiento en gl_entry.
No se crea comprobante contable real.
Solo se cambia el estado de la plantilla a aprobado.
5.2 Aplicación sí genera comprobante contable

Cuando el comprobante recurrente se aplica a un periodo:

Se genera un comprobante contable real.
Ese comprobante se comporta igual que un comprobante manual.
Se generan entradas reales en el ledger.
El comprobante generado queda vinculado al comprobante recurrente origen.
5.3 Comprobante generado

El comprobante generado debe tener:

is_recurrent = true.
recurrent_template_id.
recurrent_application_id.
Periodo contable aplicado.
Badge visual: “Recurrente”.
Mismo comportamiento contable que un comprobante manual.
Mismas validaciones de balance.
Mismo proceso de auditoría.
Misma capacidad de consulta, impresión y drill-down.
6. Tabla Intermedia de Aplicación por Periodo

Debe existir una tabla intermedia para controlar qué comprobantes recurrentes ya fueron aplicados por periodo.

Nombre sugerido:

recurring_journal_application

6.1 Propósito

Garantizar que un comprobante recurrente solo pueda aplicarse una vez por periodo contable.

6.2 Campos mínimos
ID.
Compañía.
Ledger / libro contable.
ID del comprobante recurrente.
Año fiscal.
Periodo contable.
Mes.
Fecha de aplicación.
Estado de aplicación.
ID del comprobante contable generado.
Usuario que aplicó.
Fecha y hora de ejecución.
Resultado.
Mensaje de error, si aplica.
Hash o firma de control opcional.
Creado en.
Actualizado en.
6.3 Estados de aplicación

Estados sugeridos:

pending
applied
failed
reversed
skipped
6.4 Restricción única obligatoria

Debe existir una restricción única sobre:

company_id + ledger_id + recurring_journal_id + fiscal_year + accounting_period

Esto garantiza que no se pueda aplicar dos veces el mismo comprobante recurrente en el mismo periodo.

1. Asistente de Cierre Mensual
7.1 Objetivo

Implementar un Asistente de Cierre Mensual como flujo guiado para ejecutar actividades necesarias al cierre del mes.

Por ahora, el primer y único paso será:

Aplicar comprobantes recurrentes del mes actual.

1. Paso 1: Aplicar Comprobantes Recurrentes
8.1 Pantalla del asistente

El sistema debe mostrar:

Compañía.
Año fiscal.
Periodo actual.
Fecha de cierre sugerida.
Lista de comprobantes recurrentes aplicables.
Estado de cada comprobante recurrente para el periodo.
Acción para aplicar individualmente.
Acción para aplicar todos los pendientes.
8.2 Clasificación visual

Cada comprobante recurrente debe mostrarse con estado visual:

Pendiente de aplicar.
Ya aplicado.
No aplicable.
Fallido.
Completado.
Cancelado.
8.3 Aplicación masiva

El usuario debe poder ejecutar:

Aplicar todos los comprobantes recurrentes pendientes del periodo actual.

El sistema debe:

Validar cada plantilla.
Evitar duplicados.
Generar comprobantes reales.
Registrar la aplicación en la tabla intermedia.
Mostrar resultado individual por comprobante.
Permitir revisar errores sin afectar los comprobantes exitosos.
9. Reglas de Elegibilidad

Un comprobante recurrente es aplicable si:

Está en estado aprobado.
Pertenece a la compañía seleccionada.
Pertenece al ledger seleccionado.
La fecha del periodo está entre fecha inicio y fecha fin.
No ha sido aplicado previamente en ese periodo.
Sus cuentas contables están activas.
El periodo contable está abierto.
El comprobante está balanceado.
La moneda y dimensiones son válidas.

No es aplicable si:

Está en borrador.
Está cancelado.
Está completado.
El periodo ya fue aplicado.
El periodo está cerrado.
La fecha del periodo está fuera del rango.
Tiene cuentas inactivas.
Tiene líneas inválidas o desbalanceadas.
10. Generación del Comprobante Contable

Al aplicar una plantilla recurrente, el sistema debe crear un comprobante contable real.

10.1 Fecha del comprobante

Debe definirse una regla clara.

Opciones recomendadas:

Fecha del último día del periodo.
Fecha configurada por el usuario en el asistente.
Fecha contable del periodo seleccionado.

Recomendación:

Por defecto usar el último día del periodo contable, permitiendo ajuste si el periodo sigue abierto.

10.2 Numeración

El comprobante generado debe usar la serie normal de comprobantes contables.

Debe conservar una referencia visible al comprobante recurrente origen.

Ejemplo:

Origen recurrente: DEP-MENSUAL-001
Periodo aplicado: 2026-05
11. Reversión y Anulación

Debe definirse el comportamiento si un comprobante generado necesita anularse.

Reglas recomendadas:

Si se anula el comprobante generado, la aplicación debe marcarse como reversed.
No debe eliminarse el historial.
El sistema puede permitir reaplicar el periodo solo si la aplicación anterior está reversed.
La reaplicación debe generar un nuevo comprobante.
Debe quedar trazabilidad completa.
12. Trazabilidad

Debe existir trazabilidad bidireccional.

Desde el comprobante recurrente:

Ver aplicaciones por periodo.
Ver comprobantes generados.
Ver estado de cada aplicación.
Ver usuario y fecha de ejecución.

Desde el comprobante generado:

Ver comprobante recurrente origen.
Ver periodo aplicado.
Ver aplicación asociada.
Mostrar badge “Recurrente”.
13. Auditoría

Eventos auditables mínimos:

Creación del comprobante recurrente.
Modificación en borrador.
Aprobación.
Cancelación.
Aplicación por periodo.
Fallo de aplicación.
Reversión de comprobante generado.
Marcado automático como completado.

Cada evento debe registrar:

Usuario.
Fecha y hora.
Acción.
Estado anterior.
Estado nuevo.
Comentario o motivo.
Referencia al documento afectado.
14. UI / UX
14.1 Lista de comprobantes recurrentes

Debe mostrar:

Código.
Nombre.
Compañía.
Ledger.
Fecha inicio.
Fecha fin.
Estado.
Último periodo aplicado.
Próximo periodo sugerido.
Badge de estado.
14.2 Vista detalle

Debe incluir:

Header.
Líneas contables.
Historial de aplicaciones.
Comprobantes generados.
Botones según estado.
14.3 Badges sugeridos

Para comprobantes recurrentes:

Borrador: gris.
Aprobado: azul.
Cancelado: rojo.
Completado: verde.

Para comprobantes generados:

Badge adicional: “Recurrente”.
15. Validaciones Críticas

Antes de aprobar:

Debe tener al menos dos líneas.
Debe estar balanceado.
Debe tener fecha inicio.
Debe tener fecha fin.
Fecha fin debe ser mayor o igual a fecha inicio.
Debe tener compañía.
Debe tener ledger.
Todas las cuentas deben estar activas.
Las dimensiones requeridas deben estar completas.

Antes de aplicar:

Periodo abierto.
No duplicado por periodo.
Plantilla aprobada.
Rango de fechas válido.
Balance válido.
Cuentas activas.
Permisos suficientes.
16. Seguridad y Permisos

Permisos sugeridos:

Ver comprobantes recurrentes.
Crear comprobantes recurrentes.
Editar borradores.
Aprobar comprobantes recurrentes.
Cancelar comprobantes recurrentes.
Ejecutar asistente de cierre mensual.
Aplicar comprobantes recurrentes.
Revertir aplicación recurrente.
Ver historial de aplicación.
17. Criterios de Aceptación
CA-001 — Aprobación sin afectar ledger

Dado un comprobante recurrente válido, cuando se aprueba, entonces no debe crear entradas en ledger ni comprobante contable real.

CA-002 — Aplicación desde cierre mensual

Dado un comprobante recurrente aprobado, cuando se ejecuta el paso de cierre mensual, entonces debe generarse un comprobante contable real para el periodo actual.

CA-003 — Prevención de duplicados

Dado un comprobante recurrente ya aplicado en un periodo, cuando se intenta aplicar nuevamente, entonces el sistema debe bloquear la operación.

CA-004 — Tabla intermedia obligatoria

Cada aplicación debe registrarse en la tabla intermedia con compañía, ledger, comprobante recurrente, periodo y comprobante generado.

CA-005 — Comprobante generado equivalente a manual

El comprobante generado debe comportarse igual que un comprobante manual, salvo por la bandera is_recurrent = true y sus referencias de origen.

CA-006 — Badge visual

Todo comprobante generado desde una plantilla recurrente debe mostrar un badge visual “Recurrente”.

CA-007 — Estado completado

Cuando se aplique el último periodo definido por fecha fin, el comprobante recurrente debe cambiar automáticamente a completado.

CA-008 — Cancelación controlada

Un comprobante recurrente cancelado no debe poder aplicarse a nuevos periodos.

CA-009 — Periodo cerrado

No debe permitirse aplicar comprobantes recurrentes en periodos cerrados.

CA-010 — Reversión trazable

Si se anula un comprobante generado por recurrencia, la aplicación debe conservar historial y marcarse como revertida.

1. Recomendación de Implementación

La arquitectura recomendada es separar tres conceptos:

RecurringJournalTemplate
    Define la plantilla recurrente.

RecurringJournalApplication
    Controla la aplicación por periodo.

JournalEntry
    Representa el comprobante contable real generado.

Esto mantiene limpia la contabilidad, evita duplicados y permite que el Asistente de Cierre Mensual crezca en el futuro sin convertir cada proceso de cierre en un módulo aislado.
