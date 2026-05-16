Requerimiento — Nuevo reporte: Resumen de Movimiento por Cuenta
1. Objetivo

Implementar un nuevo reporte financiero llamado:

Resumen de Movimiento por Cuenta

El reporte debe funcionar como una sábana contable plana, similar a una Balanza de Comprobación, pero orientada al análisis flexible de movimientos por cuenta.

Debe permitir al usuario:

Ver saldos resumidos por cuenta contable.
Agregar o quitar columnas dinámicamente.
Guardar múltiples layouts personalizados.
Descargar el reporte en Excel/CSV.
Reutilizar los mismos filtros del Detalle de Movimiento Contable.
Modelar distintas vistas del mismo reporte sin crear reportes separados.
2. Concepto funcional

El reporte resume los movimientos contables agrupados por cuenta.

Cada fila representa una cuenta contable.

Por defecto debe mostrar:

Código de Cuenta	Nombre de Cuenta	Saldo Inicial	Débitos	Créditos	Saldo Final

Regla de saldos:

Saldo positivo = saldo deudor
Saldo negativo = saldo acreedor

Esto aplica tanto para:

Saldo inicial
Saldo final
3. Relación con reportes existentes

Este reporte debe compartir base lógica con:

Detalle de Movimiento Contable
Balanza de Comprobación
Framework centralizado de reportes financieros

No debe implementarse como cálculo aislado.

Debe usar la misma fuente contable, filtros y reglas de cálculo del motor financiero común.

4. Filtros

Debe compartir básicamente los mismos filtros del Detalle de Movimiento Contable.

Filtros mínimos:

Compañía
Libro contable
Período contable
Rango de fechas
Cuenta contable
Rango de cuentas
Centro de costos
Unidad de negocio
Proyecto
Tipo de tercero
Tercero
Tipo de comprobante
Estado
Moneda
ID visible del comprobante
5. Columnas por defecto

El layout inicial debe incluir:

Campo	Descripción
Código de Cuenta	Código contable de la cuenta
Nombre de Cuenta	Nombre descriptivo de la cuenta
Saldo Inicial	Saldo anterior al período filtrado
Débitos	Débitos dentro del período filtrado
Créditos	Créditos dentro del período filtrado
Saldo Final	Saldo inicial + débitos - créditos
6. Columnas dinámicas

El usuario debe poder agregar o quitar columnas desde un selector de columnas.

Columnas sugeridas:

Código de cuenta
Nombre de cuenta
Nivel de cuenta
Tipo de cuenta
Sección contable
Moneda
Compañía
Libro contable
Saldo inicial
Débitos
Créditos
Saldo final
Cantidad de movimientos
Primer movimiento
Último movimiento
Centro de costos
Unidad de negocio
Proyecto
Tercero
Tipo de tercero
Tipo de comprobante
7. Layouts guardados

El usuario debe poder guardar múltiples layouts del reporte.

Cada layout debe conservar:

Nombre del layout
Columnas visibles
Orden de columnas
Ancho de columnas
Ordenamiento aplicado
Filtros guardados, si el usuario decide incluirlos
Agrupaciones, si existen
Formato numérico
Idioma de etiquetas del layout

Ejemplos:

Default
Resumen por Cuenta
Resumen por Cuenta y Centro de Costos
Resumen por Cuenta y Proyecto
Resumen por Cuenta y Tercero
Auditoría por Libro Contable
8. Internacionalización de layouts

Los layouts definidos por el usuario deben poder descargarse o visualizarse fácilmente en inglés.

Ejemplo:

Código de Cuenta → Account Code
Nombre de Cuenta → Account Name
Saldo Inicial → Opening Balance
Débitos → Debits
Créditos → Credits
Saldo Final → Ending Balance

La traducción debe aplicarse a:

Encabezados de columnas
Nombre de campos estándar
Totales
Subtotales
Etiquetas del reporte

No se deben traducir valores propios del usuario, como nombres de cuentas o nombres de centros de costo.

9. Exportación

El reporte debe permitir exportar:

Excel
CSV

La exportación debe respetar:

Layout seleccionado
Columnas visibles
Orden de columnas
Filtros aplicados
Idioma seleccionado
Formato numérico

Excel debe ser el formato principal para análisis externo.

10. Navegación

Cada fila debe permitir navegación hacia el Detalle de Movimiento Contable.

Al hacer clic en una cuenta, el sistema debe abrir:

/reports/account-movement

con filtros preaplicados:

Compañía
Libro contable
Período o rango de fechas
Cuenta contable
Estado
Moneda
Dimensiones seleccionadas
11. Diferencia con Balanza de Comprobación

La Balanza de Comprobación debe orientarse a presentación contable tradicional.

El Resumen de Movimiento por Cuenta debe orientarse a análisis flexible.

Balanza de Comprobación = reporte financiero tradicional
Resumen de Movimiento por Cuenta = sábana analítica configurable
12. Criterios de aceptación
CA-001 — Reporte disponible

Debe existir un nuevo reporte llamado Resumen de Movimiento por Cuenta.

CA-002 — Tabla plana

El reporte debe mostrarse como tabla plana, no como árbol jerárquico.

CA-003 — Columnas por defecto

Debe mostrar por defecto:

Código de Cuenta
Nombre de Cuenta
Saldo Inicial
Débitos
Créditos
Saldo Final
CA-004 — Regla de signo

Los saldos deben mostrarse así:

positivo = deudor
negativo = acreedor
CA-005 — Filtros compartidos

Debe compartir los filtros principales del Detalle de Movimiento Contable.

CA-006 — Columnas configurables

El usuario debe poder agregar, quitar y reordenar columnas.

CA-007 — Layouts múltiples

El usuario debe poder guardar múltiples layouts del reporte.

CA-008 — Exportación según layout

Excel y CSV deben exportar exactamente las columnas visibles del layout seleccionado.

CA-009 — Traducción a inglés

Los layouts deben poder visualizarse o descargarse en inglés sin modificar la definición original del usuario.

CA-010 — Navegación a movimientos

Al hacer clic en una cuenta, debe abrirse el Detalle de Movimiento Contable filtrado por esa cuenta.

13. Resultado esperado

El nuevo reporte debe permitir crear una sábana financiera flexible, exportable y reutilizable, sin duplicar lógica contable.

La idea central:

Un solo motor financiero.
Un reporte plano configurable.
Muchos layouts útiles listos para exportar a excel

Un solo motor financiero.
Un reporte plano configurable.
Muchos layouts útiles.
