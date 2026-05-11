Estado 2026-05-11: issues implementados y cubiertos con pruebas focalizadas. Se conserva el detalle historico debajo como referencia de la iteracion.

Para trabajar en estos issues primeto debes cargar el contexto disponible de:

- AGENTS.md
- ESTADO_ACTUAL.md
- SESSIONS.md
- PENDIENTE.md

Los siguientes directorios contienen contexto adicional:

- .github/instructions
- modulos

Al finalizar cada iteración actualiza:

- ESTADO_ACTUAL.md
- SESSIONS.md
- PENDIENTE.md


Issues actuales que deben corregirse:

## En el menú de contabilidad agregar Comprobantes Contables de Cierre

Lo que yo haría es agregar un query en la URL /accounting/journal/new?isclosing=true

si isclosing es verdadero marcar el selector de etapa de cierre como Cierre

## En los reportes eliminar los dos botones al final

Ahorra que en la parte superior estas las opciones para guardar o cargar layouts al final del
formulario los botones de Guardar Vista y Eliminar Vista se deben eliminar

## Toggle de Mostrar/Ocultar filtros avanzados no funciona

Los filtros avanzados deben estar dentro de un contenedor que reponda a Mostrar / Ocultar filtros avanzados

## Busqueda de tercero no funciona

El selector de tipo de tercero muestra supplier/customer la busqueda de terceros no funciona

## Agrupar por tipo de comprobante no funciona

No funciona el agrupador por comprobante

## Mover el filtro de Comprobante dentro de los filtros avanzados

## En las vistas de Balanza de Comprobación, Balance General y Estado de Resultado

1. Ocultar el selector de columnas visibles
2. Filtros avanzados colapsados por defecto

## Prefill filtros al seleccionar la compañia o en la carga inicial

1. Cargar Libro Fiscal por defecto
2. Seleccionar periodo contable en base a la fecha actual

## Incluir en pruebas unitarias pruebas de stress en reportes

Estresa los reportes con multiple filtros haz una prueba end to end de reportes financieros
