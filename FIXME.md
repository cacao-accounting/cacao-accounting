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

## /accounting/journal/recurring

Agregar botón "Nueva Plantilla"
Agregar lista de plantillas de comprobantes recurrentes.

## /accounting/period-close/monthly

No queda claro como iniciar el proceso de cierre mensual
Agregar botón "Nuevo Cierre"
Agregar lista de cierres

## /accounting/account/new

Seguir el UX definido en la implementación de comprobantes contables
Eliminar campo de Moneda. La multimoneda la maneja el backend
Hay dos selectores de Tipo, uno esta vacío y debe eliminarse el otro debe completarse con los tipos de cuenta que requiere el sistema: cacao_accounting/contabilidad/ctas/catalogos/base_en.json el tipo de cuenta no es requerido para crear una cuenta
Activo y Habilitado esta duplicado dejar solo un campo visible
Selector de cuenta padre debe actualizarse para usar smart-select filtrando solo cuentas de la compañia de la misma clasificación y que sean cuentas de grupo

## /accounting/account/<compañia>/<codigo_cuenta>

Actualizar la vista para visualizar una cuenta para seguir el UX de la implementación de comprobantes contables
Agregar botones "Editar" y "Cancelar"

## Al crear una nueva compañia se debe de crear un centro de costos por defecto

Aplicar las mismas mejoras visuales que a la implementación de cuentas contables

## /accounting/entity/<code>

Aplicar mismo UX que la implementación de comprobante contable 

## /accounting/entity/edit/<code>

Aplicar el mismo UX que la implementación de comprobante contable

## /accounting/entity/new

Aplicar el mismo UX que la implementación de comprobante contable

## Actualizar el UX de la implementación de comprobante contable para Unidades de Negocio, Libros Contabilidad, Proyectos, Monedas, Tipos de Cambio, Periodos Contables y Años Fiscales

El UX debe ser uniforme en todo el modulo de contabilidad, tomando como base el UX de la implementación de comprobantes contables

Las paginas que muestran listados necesitan contar con filtros apropiados para facilitar localizar registros sin tener que navegar todos los registros.





