Requerimiento Formal de Desarrollo

Migración UX del módulo de Bancos utilizando el patrón de Comprobante Contable

Objetivo

Rediseñar y migrar los formularios y vistas del módulo de Bancos para utilizar el mismo patrón visual, estructura de interacción y experiencia de usuario implementada en:

cacao_accounting/contabilidad/templates/contabilidad/journal_nuevo.html

cacao_accounting/contabilidad/templates/contabilidad/journal.html


La implementación debe priorizar simplicidad, mantenibilidad y consistencia visual, evitando macros complejas, lógica duplicada y sobre ingeniería.


---

Alcance

El alcance incluye:

1. Formularios de creación y edición.


2. Vistas de detalle.


3. Flujo de captura de transacciones bancarias.


4. Validaciones UX básicas.


5. Integración con Smart Select.


6. Adaptación visual y estructural al patrón del comprobante contable.



No incluye:

Reescritura del motor contable.

Automatización avanzada de conciliación.

Procesos batch.

Integraciones bancarias.

Workflow de aprobación.



---

Objetivos Funcionales

El módulo de Bancos deberá soportar cuatro transacciones principales:

1. Pago


2. Nota de Débito


3. Nota de Crédito


4. Transferencia entre cuentas



Todas las transacciones deben compartir una experiencia de usuario uniforme.


---

Lineamientos Generales de UX

Patrón de referencia

La interfaz debe reutilizar el mismo patrón UX/UI del comprobante contable:

Header superior de captura.

Formulario dividido por bloques funcionales.

Tabla dinámica de detalle.

Inputs alineados horizontalmente.

Navegación rápida por teclado.

Smart Select para relaciones dependientes.

Minimizar navegación entre pantallas.

Flujo centrado en captura rápida operativa.



---

Requerimientos Globales

Selección inicial obligatoria

Toda transacción debe iniciar con:

1. Selección de compañía.


2. Selección de serie o secuencia.



Estos campos gobiernan el resto del formulario.


---

Moneda automática

La moneda:

Debe obtenerse automáticamente desde la cuenta bancaria seleccionada.

Debe mostrarse en pantalla en modo lectura.

No debe ser editable manualmente.



---

Smart Select

Debe utilizarse Smart Select en:

Cuenta bancaria.

Serie/secuencia.

Cliente.

Proveedor.

Cuenta origen.

Cuenta destino.


La selección dependiente debe filtrar registros según:

Compañía seleccionada.

Tipo de transacción.

Tipo de tercero.

Moneda cuando aplique.



---

Requerimientos por Transacción


---

1. Pago

Objetivo

Registrar pagos entrantes o salientes asociados a clientes, proveedores o transferencias operativas.


---

Campos requeridos

Encabezado

Compañía

Serie o secuencia

Cuenta bancaria

Fecha de transacción

Tipo de pago:

Pago entrante

Pago saliente


Forma de pago:

Cheque

Transferencia




---

Manejo de chequera

Reglas

Si:

El pago es saliente

La forma de pago es cheque

La cuenta bancaria tiene chequera asociada


Entonces:

El sistema debe proponer automáticamente el próximo número de cheque disponible.



---

UX requerida

El usuario:

Debe poder visualizar claramente el número propuesto.

Debe poder confirmar que coincide con la secuencia física de la chequera antes de grabar.



---

Restricciones

Pagos por transferencia:

No afectan la secuencia de chequera.

No deben consumir números de cheque.



---

Información del tercero

Campos requeridos

Tipo de tercero:

Cliente

Proveedor


Tercero



---

Monto

El monto:

Debe ingresarse en la moneda de la cuenta bancaria seleccionada.

Debe validar precisión decimal según la moneda.



---

Asociación de pagos

Debe existir una tabla de asociación entre pagos y documentos.


---

Reglas funcionales

Un pago puede:

Aplicarse a uno o varios documentos individuales.

Quedar parcialmente aplicado.

Quedar completamente sin aplicar.

Registrarse como anticipo o transferencia.



---

Tabla de asociación requerida

La tabla debe permitir:

Seleccionar documentos pendientes.

Visualizar:

referencia

fecha

saldo pendiente

moneda

monto aplicado


Aplicar montos parciales.



---

2. Nota de Débito

Objetivo

Registrar disminuciones del saldo bancario.


---

Campos requeridos

Compañía

Serie o secuencia

Cuenta bancaria

Fecha

Cuenta contable

Descripción

Monto



---

Reglas

Solo requiere seleccionar una cuenta contable.

El monto debe ingresarse en la moneda de la cuenta bancaria.

La operación disminuye el saldo de la cuenta bancaria.



---

3. Nota de Crédito

Objetivo

Registrar incrementos del saldo bancario.


---

Campos requeridos

Compañía

Serie o secuencia

Cuenta bancaria

Fecha

Cuenta contable

Descripción

Monto



---

Reglas

Solo requiere seleccionar una cuenta contable.

El monto debe ingresarse en la moneda de la cuenta bancaria.

La operación aumenta el saldo de la cuenta bancaria.



---

4. Transferencia entre cuentas

Objetivo

Registrar movimientos entre cuentas bancarias propias.


---

Campos requeridos

Compañía

Serie o secuencia

Cuenta origen

Cuenta destino

Fecha de posteo

Monto origen

Descripción



---

Reglas de moneda

Las cuentas:

Pueden tener monedas distintas.

El monto ingresado corresponde a la moneda de la cuenta origen.



---

Conversión monetaria

La conversión:

Debe manejarse exclusivamente en backend.

Debe utilizar el tipo de cambio vigente para la fecha de posteo.



---

Validación obligatoria

Si no existe tipo de cambio para la fecha:

El sistema debe impedir el posteo.

Debe mostrarse advertencia clara al usuario.



---

Requerimientos de Backend


---

Contabilización

Todas las transacciones:

Deben generar comprobante contable automáticamente.

Deben mantener trazabilidad hacia el origen bancario.



---

Atomicidad

Las operaciones:

Deben ejecutarse dentro de transacciones de base de datos.

No deben permitir estados parciales.



---

Validaciones mínimas

Generales

Cuenta bancaria activa.

Serie activa.

Fecha válida.

Monto mayor que cero.



---

Pagos

Validar disponibilidad de chequera.

Validar correlativo de cheque.

Validar saldo pendiente de documentos aplicados.



---

Transferencias

Validar cuenta origen distinta de cuenta destino.

Validar tipo de cambio existente.



---

Requerimientos de Vistas

Vista de listado

Todas las transacciones deben utilizar una vista homogénea con:

Fecha

Número

Tipo

Cuenta bancaria

Moneda

Monto

Estado

Usuario creador



---

Vista detalle

Debe mostrar:

Encabezado completo.

Información contable asociada.

Asociación de documentos.

Historial básico.

Totales y moneda.



---

Requerimientos Técnicos

Arquitectura

La implementación debe:

Reutilizar componentes existentes del módulo contable.

Reutilizar estilos y estructura HTML del journal.

Evitar duplicación innecesaria.



---

Restricciones explícitas

No utilizar:

Macros complejas.

Formularios excesivamente dinámicos.

JavaScript pesado.

Componentes SPA.

Dependencias frontend adicionales innecesarias.



---

Objetivo Final de UX

El usuario debe percibir el módulo de Bancos como:

Consistente con Contabilidad.

Operativamente rápido.

Claro para digitación masiva.

Fácil de mantener.

Predecible.

Sin fricción visual ni funcional.
