Issues identificados
BUG-001 — Error al asignar cuenta padre al crear cuenta contable

Severidad: Alta
Módulo: Contabilidad / Catálogo de cuentas
Pantalla: Nueva Cuenta Contable

Problema

Al crear una cuenta contable nueva, el formulario muestra una cuenta padre existente:

11.01.002 - Cuentas bancarias

Pero al guardar, el sistema rechaza el registro con el mensaje:

La cuenta padre indicada no existe para la entidad seleccionada.

Esto indica una inconsistencia entre el dato seleccionado en frontend y la validación del backend.

Causa probable

Una o varias de estas condiciones:

El campo visible muestra texto, pero el formulario no está enviando el id real de la cuenta padre.
El Smart Select no está sincronizando correctamente el valor oculto.
La búsqueda de cuenta padre no está filtrando correctamente por entidad.
El backend espera parent_id, pero el formulario envía parent_account, parent_code, texto visible, o un valor incompatible.
Al recargar el formulario después del error, se pierde la entidad seleccionada, lo cual agrava el problema porque el padre ya no puede validarse contra entidad.
Requerimiento de corrección

El campo Cuenta Padre debe comportarse como un selector controlado de cuentas contables existentes, no como texto libre.

Debe enviar al backend el identificador único de la cuenta padre, preferiblemente parent_id.

El backend debe validar:

Que la cuenta padre existe.
Que pertenece a la misma entidad/compañía seleccionada.
Que no genera una relación circular.
Que la cuenta padre puede recibir hijos, si existe una regla de “cuenta de grupo”.
Que no se pueda asignar como padre una cuenta de otra entidad.
Criterios de aceptación
Al seleccionar una cuenta padre existente y guardar, la cuenta nueva se crea correctamente.
Si no se selecciona cuenta padre, se permite crear una cuenta raíz cuando aplique.
Si se manipula el request y se envía un parent_id inválido, el backend rechaza la operación.
Si se envía un parent_id de otra entidad, el backend rechaza la operación.
Después de un error de validación, el formulario conserva:
entidad seleccionada,
código,
nombre,
clasificación,
tipo de cuenta,
cuenta padre,
estado activo,
bandera de cuenta de grupo.
El campo de cuenta padre debe mostrar resultados filtrados por la entidad seleccionada.
Si el usuario cambia la entidad, el campo cuenta padre debe limpiarse automáticamente.
Test obligatorio

Agregar test unitario o funcional para bloquear regresión:

Crear entidad A.
Crear entidad B.
Crear cuenta padre en entidad A.
Crear cuenta hija en entidad A usando parent_id válido.
Confirmar que se guarda correctamente.
Intentar crear cuenta hija en entidad B usando el parent_id de entidad A.
Confirmar rechazo con error controlado.
BUG-002 — No se puede seleccionar centro de costos padre al crear centro de costos

Severidad: Alta
Módulo: Contabilidad / Centros de costos
Pantalla: Nuevo Centro de Costos

Problema

El campo Centro Padre no funciona como un buscador/selector real. En la captura se observa que acepta texto como m, pero no resuelve ni selecciona un centro de costos existente.

Esto impide construir jerarquías de centros de costos.

Causa probable

Una o varias de estas condiciones:

El campo está implementado como input de texto simple.
Falta endpoint de búsqueda para centros de costos padre.
El endpoint existe, pero no está conectado al formulario.
El formulario no envía parent_id.
El backend espera un ID, pero recibe texto.
No se filtran centros de costos por entidad.
Requerimiento de corrección

El campo Centro Padre debe implementarse con el mismo patrón funcional esperado para Smart Select.

Debe permitir buscar centros de costos existentes por:

código,
nombre,
entidad seleccionada.

Debe enviar al backend el parent_id real del centro de costos seleccionado.

El backend debe validar:

Que el centro padre existe.
Que pertenece a la misma entidad.
Que no genera relación circular.
Que el centro padre puede recibir hijos, si aplica la regla de centro de grupo.
Que no se use como padre un centro de otra entidad.
Criterios de aceptación
El usuario puede buscar un centro padre por código o nombre.
El selector muestra resultados existentes.
Al seleccionar un centro padre y guardar, el nuevo centro de costos queda relacionado correctamente.
Si la entidad cambia, el centro padre seleccionado se limpia.
No se permite usar como padre un centro de costos de otra entidad.
No se permite crear ciclos jerárquicos.
Después de un error de validación, el formulario conserva los datos ingresados.
Test obligatorio

Agregar test unitario o funcional:

Crear entidad A.
Crear centro padre en entidad A.
Crear centro hijo usando parent_id válido.
Confirmar que la relación padre-hijo se guarda correctamente.
Crear entidad B.
Intentar usar el centro padre de entidad A en entidad B.
Confirmar rechazo.
Intentar crear relación circular.
Confirmar rechazo.
UX-001 — Formulario de períodos contables es confuso

Severidad: Media
Módulo: Contabilidad / Períodos contables
Pantalla: Editar Período Contable

Problema

El formulario actual muestra:

Estado (Etiqueta) con valor textual, por ejemplo open.
checkbox Habilitado.
checkbox Cerrado.

Esto genera ambigüedad porque el usuario ve tres formas de representar estado:

estado textual,
habilitado/deshabilitado,
abierto/cerrado.

La pantalla debería expresar claramente dos conceptos independientes:

si el período está disponible para operación;
si el período está abierto o cerrado contablemente.
Requerimiento de corrección

Centralizar la gestión del período contable en dos dimensiones explícitas:

1. Estado operativo

Valores permitidos:

habilitado
deshabilitado

Este estado determina si el período puede ser usado por el sistema.

2. Estado contable

Valores permitidos:

abierto
cerrado

Este estado determina si se pueden registrar/postear transacciones contables en el período.

Cambio recomendado en formulario

Eliminar o esconder del formulario el campo textual:

Estado (Etiqueta)

Reemplazarlo por controles claros:

Estado operativo:
Selector o radio buttons:

Habilitado
Deshabilitado

Estado contable:
Selector o radio buttons:

Abierto
Cerrado

No usar simultáneamente input textual y checkboxes para representar el mismo concepto.

Reglas funcionales sugeridas
Un período deshabilitado no debe estar disponible para nuevas transacciones.
Un período cerrado no debe aceptar nuevos postings.
Un período puede estar:
habilitado y abierto,
habilitado y cerrado,
deshabilitado y abierto,
deshabilitado y cerrado.
Para efectos prácticos, una transacción solo debería poder registrarse si el período está:
habilitado,
abierto.
Criterios de aceptación
El formulario ya no muestra Estado (Etiqueta) como campo editable libre.
El usuario puede definir claramente si el período está habilitado o deshabilitado.
El usuario puede definir claramente si el período está abierto o cerrado.
El backend valida que solo se acepten valores válidos.
El sistema no permite registrar transacciones en períodos cerrados.
El sistema no permite registrar transacciones en períodos deshabilitados.
Los listados deben mostrar ambos estados de forma clara:
Operativo: Habilitado / Deshabilitado.
Contable: Abierto / Cerrado.
Test obligatorio

Agregar tests para:

Crear período habilitado y abierto.
Registrar transacción en período habilitado y abierto: debe permitir.
Intentar registrar transacción en período habilitado y cerrado: debe bloquear.
Intentar registrar transacción en período deshabilitado y abierto: debe bloquear.
Intentar registrar transacción en período deshabilitado y cerrado: debe bloquear.
Editar período y validar persistencia correcta de ambos estados.
