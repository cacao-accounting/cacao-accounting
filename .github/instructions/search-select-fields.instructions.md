---
applyTo: "**/templates/**/*.html"
---

# Campos de selección de registros existentes

Usa el Smart Select Framework cuando un formulario permita seleccionar datos ya existentes del sistema y el catálogo pueda crecer, depender de contexto o requerir filtros de negocio.

## Cuándo usarlo

- Cuentas contables, clientes, proveedores, ítems, bodegas, cuentas bancarias, series/documentos origen y cualquier catálogo amplio.
- Campos dependientes de compañía, tipo de cuenta, tipo de tercero, estado, documento origen u otro campo padre.
- Formularios móviles o de captura rápida donde un `<select>` nativo degrade la experiencia.

Mantén `<select>` tradicional solo para listas pequeñas, fijas y cerradas en código, como estados simples o tipos de documento.

## Contrato frontend

- Cargar una sola librería: `static/js/smart-select.js`.
- Inicializar cada campo con `x-data="smartSelect({...})"`.
- Guardar siempre el identificador real en un `<input type="hidden">`; el texto visible es solo búsqueda/etiqueta.
- Pasar mensajes visibles desde Jinja con `_()` y `tojson`.
- Definir filtros desde el HTML:
  - valores fijos: `filters: { account_type: ["bank"] }`
  - filtros por campo padre: `filters: { company: { selector: "#company" } }`
  - registrar el selector padre en `filterSources` para limpiar selección cuando cambie.
- No cargar todas las opciones en el HTML para catálogos grandes.

## Contrato backend

- Toda búsqueda debe pasar por `GET /api/search-select`.
- El backend debe usar un registry explícito; nunca consultar tablas arbitrarias por nombre enviado desde el cliente.
- Cada doctype debe declarar:
  - modelo permitido,
  - campos de búsqueda,
  - filtros permitidos,
  - filtros por defecto,
  - etiqueta segura para el usuario,
  - límite de resultados.
- Validar filtros recibidos y rechazar cualquier filtro no declarado.
- Respetar aislamiento por compañía y no exponer datos sensibles.
- Mantener la validación final en servicios backend; Smart Select mejora UX, no reemplaza reglas de negocio.

## UX esperada

- Buscar solo después de `minChars`.
- Mostrar carga, error, sin resultados y selección inválida cerca del campo.
- Limpiar selección cuando cambian filtros padre.
- Permitir buscar por código, nombre o descripción según el doctype.
- Priorizar coincidencias que empiezan con el texto escrito.
- Funcionar de forma consistente en escritorio y móvil.

## Migración incremental

- Migrar un formulario a la vez.
- En cada migración, agregar primero el doctype/filtro al registry si falta.
- Reemplazar solo los `<select>` de catálogos grandes o contextuales.
- Añadir pruebas de servicio/API para los filtros críticos del formulario.
- Confirmar que el POST guarda el ID real y que las validaciones backend existentes siguen bloqueando combinaciones inválidas.
