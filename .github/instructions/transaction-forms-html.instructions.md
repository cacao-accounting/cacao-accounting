---
applyTo: "**/templates/**/*.html"
---

# Cacao Accounting HTML Instructions

Utiliza el formulario de nuevo asiento contable como referencia estructural para el diseño de formularios transaccionales en el módulo de contabilidad. Mantén la separación clara entre header, grilla de líneas y memo, y sigue las convenciones de filas por índice y campos por prefijo de fila. Asegúrate de que las acciones por línea sean visibles en la grilla y que el detalle adicional por línea esté colapsado para campos avanzados. Mantén los metadatos de línea ocultos para trazabilidad sin sobrecargar la grilla principal.

## Formularios transaccionales

Estas reglas aplican a formularios de documentos transaccionales (asientos, facturas, pagos, recepciones, entregas, movimientos de inventario).

## Referencia base actual

Tomar como referencia estructural el formulario de asientos en:

- cacao_accounting/contabilidad/templates/contabilidad/journal_nuevo.html
- cacao_accounting/contabilidad/templates/contabilidad/journal.html

Patrones concretos a conservar/evolucionar desde esa referencia:

- Separación clara de áreas por bloques:
  - `new-GL-HEADER` para cabecera.
  - `new-GL-ROWS` para grilla de líneas.
  - `new-GL-MEMO` para observaciones generales.
- Convención de filas por índice (`gl-row-{n}`) y campos por prefijo de fila (`gl-row-{n}-FIELD`).
- Acciones por línea visibles en grilla:
  - expandir detalles,
  - eliminar,
  - futuras acciones: duplicar, insertar arriba/abajo, mover.
- Detalle adicional por línea con colapso (`collapse`) para campos avanzados.
- Metadatos de línea ocultos para trazabilidad (`ID`, `ORDER`, `TIPO`) sin sobrecargar la grilla principal.

## Estructura visual obligatoria

- Mostrar claramente dos bloques principales:
  - Header del documento.
  - Tabla de items/líneas.
- El header debe contener campos críticos de contexto:
  - tipo de documento,
  - compañía,
  - fecha de contabilización,
  - serie/secuencia,
  - moneda,
  - estado.
- La tabla de items debe ocupar el foco principal de captura.

## Grilla de items: columnas por defecto

- La grilla debe mostrar solo los campos más usados para captura rápida.
- Evitar saturar la grilla con campos secundarios.
- Definir un set base de columnas por tipo de formulario.
- Mantener anchos de columna compactos para entrada eficiente.

Para asientos contables, usar por defecto una grilla mínima equivalente a:

- Cuenta.
- Centro de costos.
- Tipo de entidad (si aplica al flujo).
- Tercero (si aplica al flujo).
- Debe.
- Haber.

Campos como proyecto, unidad, moneda, tipo de cambio, referencias internas y observaciones de línea deben ir en panel expandido.

## Detalle expandible por línea

- Campos menos frecuentes deben mostrarse en modo expandir/colapsar por línea.
- La edición expandida debe incluir:
  - dimensiones contables,
  - referencias,
  - observaciones,
  - metadatos avanzados,
  - flags de comportamiento (ejemplo: es anticipo).
- La información avanzada no debe bloquear la captura rápida en la grilla.
- El panel expandido debe mantener consistencia de orden de campos entre formularios equivalentes.

## Configuración de columnas por usuario

- El usuario puede elegir qué columnas ver en la grilla por formulario.
- La configuración debe ser persistente por:
  - usuario,
  - tipo de formulario.
- Debe permitir:
  - agregar columnas,
  - quitar columnas,
  - reordenar columnas,
  - definir ancho relativo de columna.
- Debe existir opción de reset a configuración por defecto.

Persistencia mínima recomendada:

- Clave por usuario + tipo de formulario + vista (draft/edit/review).
- Versión de esquema de columnas para migración futura cuando cambie el formulario.

## Operaciones de líneas obligatorias

- Soportar insertar línea abajo y arriba.
- Soportar duplicar línea.
- Soportar eliminar línea.
- Soportar mover/reordenar líneas.
- Soportar agregar múltiples líneas en lote.
- Todas las acciones deben operar sobre el índice real de la línea para evitar borrar/modificar líneas incorrectas.
- Evitar hardcode de cantidad fija de filas; usar plantilla dinámica de línea clonable.

## UX y productividad

- Preferir formularios de alta velocidad de digitación.
- Minimizar clics para completar un documento estándar.
- Mantener acciones primarias visibles (guardar, enviar, cancelar).
- Mantener consistencia de layout entre todos los formularios transaccionales.

## Reglas de validación visual

- Campos obligatorios deben estar claramente marcados.
- Errores de validación deben mostrarse cerca del campo/línea con problema.
- Totales (debe/haber, subtotal/impuestos/total, saldo) deben actualizarse en tiempo real.
- En asientos contables, mostrar estado de balance de manera explícita.
- Validar por línea que no existan `debe` y `haber` simultáneamente con valor positivo.
- Validar al guardar que el total `debe` sea igual al total `haber`.

## Integración funcional esperada

- La grilla y el detalle expandido deben reflejar reglas de negocio del documento.
- Debe soportar escenarios reales:
  - anticipos parciales y totales,
  - impuestos fijos y porcentuales,
  - cargos aditivos y deductivos,
  - devoluciones,
  - notas de crédito/débito,
  - correcciones de UOM y precio.

## Auditoría y trazabilidad de cambios de UI

- Cambios de configuración de columnas no deben alterar datos transaccionales.
- Preferir registrar cambios de preferencia de columnas para troubleshooting.
- El formulario nunca debe ocultar campos críticos de auditoría en vistas de revisión.
- El detalle expandido debe preservar accesibilidad y auditabilidad (labels, ids únicos, orden estable).

## Qué evitar

- Formularios con demasiados campos visibles en la grilla por defecto.
- Flujos que obligan a abrir pantallas secundarias para operaciones básicas de líneas.
- Personalización de columnas sin persistencia por usuario.
- Inconsistencias de comportamiento entre formularios equivalentes.
