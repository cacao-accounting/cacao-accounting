# Evidencia de controles internos en Cloud

Cacao soporta los controles ICFR del cliente; no certifica el cumplimiento de SOX.

La aplicación Cloud registra los cambios de configuración sensibles y las
transiciones de documentos financieros en `audit_trail`, usando la misma
transacción de base de datos que el cambio.

## Cadena de hashes de auditoría

Las filas nuevas de `audit_trail` llevan `payload_hash` (SHA-256 del contenido
canónico de la fila) y `prev_hash` (el `payload_hash` de la fila anterior,
ordenadas por el id ULID monotónico).
`cacao_accounting.audit_chain.verify_audit_trail_chain()` recalcula cada hash y
valida el enlazado, de modo que editar o eliminar filas históricas se detecta.
Las filas almacenadas antes de habilitar esta función no tienen hash y quedan
excluidas de la verificación. Escritores concurrentes en PostgreSQL pueden leer
el mismo `prev_hash` antes de que la otra transacción confirme y producir una
bifurcación aparente; SQLite no se ve afectado. La inmutabilidad a nivel de base
de datos (ver los GRANT de PostgreSQL abajo) sigue siendo la protección primaria
contra manipulación; la cadena de hashes es la capa de detección.

Desde Cacao 20261015 el hash (versión de cadena 2) incluye el ULID propio de la
fila en el contenido canónico, de modo que duplicar el contenido de una fila en
otra posición se detecta. Las filas selladas antes de la función llevan
`hash_version NULL` y se verifican con el formato legado; no se reescribe dato
histórico alguno.

Las bifurcaciones de escritores concurrentes en PostgreSQL aún no están
serializadas; ver el issue #926 para la hoja de ruta de endurecimiento.

### Verificación operativa

`cacaoctl audit-verify` ejecuta `verify_audit_trail_chain()` contra la base de
datos activa y reporta los hallazgos (`payload_tampered`, `chain_break`) con el
id de la fila, y termina con código 1 cuando hay hallazgos. Está pensado para
conectarse como tarea periódica (cron/systemd timer/scheduler) más monitoreo, de
modo que también se alerte la falta de ejecución:

```cron
# cada 30 minutos; el comando termina con código 1 cuando hay hallazgos.
*/30 * * * * cacaoctl audit-verify || alert-audit-chain
```

Playbook de respuesta cuando el comando reporta hallazgos:

1. Congelar el acceso que podría reescribir `audit_trail` (restringir el rol
   runtime, bloquear las instancias de la aplicación contra la base de datos).
2. Tomar un respaldo completo antes de cualquier intento de reparación; nunca
   editar filas en sitio.
3. Verificar si faltan las filas referenciadas por `document_type`/`document_id`
   (`chain_break` normalmente significa que se eliminó una fila en medio de la
   cadena).
4. Comparar `before_json`/`after_json` de las filas vecinas para establecer la
   secuencia real; usar la cola sana (filas con `payload_hash NULL`) como ancla.
5. Escalar a una revisión de incidente según la política de integridad de datos.
   La detección es el contrato del comando; la aplicación nunca recalcula el
   hash de filas históricas.

Los servicios automáticos deben envolver su trabajo en
`with audit_actor(user_id=None, name="job:exchange-import"):` de
`internal_control_service`. Sin un actor autenticado o explícito, los cambios
automáticos se identifican como `system`. Nunca use una cuenta humana compartida
para un job.

La aplicación rechaza la mutación de la evidencia de auditoría y de los valores
financieros posteados. Estas protecciones son adicionales a la autorización de
servicio; el rol runtime de la base de datos también debe restringirse. El modo
Desktop con SQLite no requiere un servicio separado.

## Evidencia de aprobaciones y configuración

`cacao_accounting.internal_control_service` instala los guardas compartidos.
Todo cambio sobre un modelo sensible (usuarios, roles, acceso por compañía,
entidades, tipos de cambio, períodos contables y años fiscales, impuestos y
reglas de impuestos, reglas de mapeo contable y cuentas por defecto, libros y
cuentas, y la configuración de matching de compras/ventas) se escribe en
`audit_trail` en la misma transacción que el cambio, con los valores
antes/después y el actor resuelto.

Las claves sensibles de `cacao_config` se reconocen por prefijo (`approval_`,
`four_eyes_`, `fiscal_`, `accounting_`). La identidad de la fila es la clave, así
que el guarda resuelve la clave persistida antes de un renombre: renombrar una
clave sensible igual produce el evento de auditoría y conserva el alcance de
compañía de la clave anterior. El `UPDATE`/`DELETE` Core directo sobre
`cacao_config` se rechaza porque la identidad sensible vive en la cláusula
`WHERE`, no en las columnas mutadas; solo la vía ORM auditada puede editarla.

Las solicitudes de aprobación llevan procedencia inmutable: `policy_snapshot`,
`review_payload`, `requested_by`, `company_id`, `required_level`, la identidad
del documento y los sellos de creación/cancelación no pueden cambiarse ni
eliminarse por ORM ni por Core. Solo se permiten las transiciones de ciclo de
vida (`status`, `current_level`), y únicamente para las filas concretas
entregadas a `approval_request_transition(...)`. Los updates masivos por ORM
(`do_orm_execute`) también se rechazan, de modo que no se puede omitir un
snapshot de configuración o aprobación.

## Despliegue en PostgreSQL

Use roles separados de propietario de migración y de runtime. El rol runtime NO
debe ser propietario de tablas, heredar el rol propietario, ser superusuario ni
tener privilegios de CREATE en el esquema. Ejecute las migraciones con la
credencial del propietario y luego ejecute lo siguiente como propietario,
reemplazando `cacao_runtime` por el rol runtime dedicado:

```sql
GRANT SELECT, INSERT ON audit_trail, approval_action, audit_log TO cacao_runtime;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_trail, approval_action, audit_log
  FROM cacao_runtime, PUBLIC;
```

La misma restricción aplica a las tablas de evidencia del flujo
inter-comprobante (`document_relation`, `purchase_reconciliation`,
`purchase_reconciliation_item`, `purchase_invoice_receipt_allocation`,
`purchase_receipt_return_allocation`, `purchase_credit_note_allocation`). La
aplicación puede anexar relaciones nuevas y escribir las transiciones de
flujo auditadas (`status` y los sellos de reversión/cancelación) mediante sus
servicios autorizados, pero bajo ninguna circunstancia son aceptables reescrituras
directas de campos de vínculo, cantidad o cálculo de matching:

```sql
GRANT SELECT, INSERT ON document_relation, purchase_reconciliation,
  purchase_reconciliation_item, purchase_invoice_receipt_allocation,
  purchase_receipt_return_allocation, purchase_credit_note_allocation
  TO cacao_runtime;
GRANT SELECT, UPDATE ON document_relation, purchase_reconciliation,
  purchase_reconciliation_item, purchase_invoice_receipt_allocation,
  purchase_receipt_return_allocation, purchase_credit_note_allocation
  TO cacao_runtime;
REVOKE DELETE, TRUNCATE ON document_relation, purchase_reconciliation,
  purchase_reconciliation_item, purchase_invoice_receipt_allocation,
  purchase_receipt_return_allocation, purchase_credit_note_allocation
  FROM cacao_runtime, PUBLIC;
```

Elimine los privilegios equivalentes heredados por otras membresías de rol.
Conceda aparte los permisos de las tablas de negocio normales. Nunca conceda
`ALL ON ALL TABLES` al rol runtime después de esta restricción. Pruebe con la
credencial runtime que SELECT/INSERT funcionan y que UPDATE/DELETE/TRUNCATE
fallan para cada tabla de evidencia. Verifique la membresía con `pg_has_role`,
la propiedad de las tablas y la herencia de privilegios durante el
aprovisionamiento; un REVOKE no anula privilegios concedidos por otros roles.

La cuenta de migración no está disponible para la aplicación en ejecución.
Mantenga las credenciales de despliegue separadas de `SQLALCHEMY_DATABASE_URI` y
restrinja el acceso de red a la base de datos. Un propietario de PostgreSQL o un
administrador de infraestructura aún puede alterar datos. Los respaldos retenidos
o las copias de evidencia fuera de los derechos de modificación de ese
administrador y los ejercicios de restauración pertenecen a los controles
operativos del SaaS.

## Revisión de cuatro ojos y autoridad de administrador

Cuando el flujo de aprobación de cuatro ojos está habilitado, el sistema exige
una revisión independiente por un usuario distinto cuyo rango de aprobación sea
al menos tan alto como el rango del preparador más alto. Esto significa que un
documento preparado por un administrador solo puede aprobarlo otro administrador
activo con la misma autoridad de módulo/compañía; no hay anulación implícita por
parte de un jefe.

Política operativa: deben existir al menos dos usuarios administradores activos
para una compañía/módulo antes de exigir una revisión de cuatro ojos. Si solo hay
un administrador disponible, la revisión no puede completarse de forma
independiente y el documento debe permanecer pendiente o reasignarse para
revisión. Los administradores no deben ser los operadores por defecto del
posteo diario cuando la política de cuatro ojos está activa; deben actuar como
revisores o aprobadores, mientras el posteo operativo se mantiene en una vía de
preparador separada.

Este valor por defecto es intencionalmente estricto y auditable:
`approver.rank >= max(preparer.rank)` con un usuario distinto, en lugar de una
excepción oculta como `rank == 3` que debilitaría la segregación de funciones.

## Verificación de release

Cacao crea su esquema con `create_all` (`cacaoctl db init`); no se aplica una
migración incremental. Las columnas `roles_access.approval_rank` y
`approval_request.policy_snapshot` / `review_payload` se crean con el esquema.
Las bases construidas con un esquema anterior deben recrearse, o agregarse las
columnas y clasificarse manualmente los roles estándar de módulo antes de
habilitar cuatro ojos. Los preparadores históricos no se infieren. Clasifique
explícitamente los roles personalizados. Las solicitudes de aprobación
existentes sin procedencia son evidencia histórica, no prueba de revisión
independiente.

Valide en PostgreSQL con credenciales runtime reales, además de las pruebas en
SQLite. Registre versión/commit, revisor, resultado del esquema y comprobaciones
de privilegios runtime en el registro de despliegue. Ninguna prueba automatizada
puede establecer el aislamiento de roles en producción, la retención de
respaldos ni la efectividad operativa de los controles de un cliente.

## Aprobaciones de configuración de matching

La política aprobada en el issue #924 es simple: todo cambio efectivo en la
configuración de matching de compras o ventas requiere aprobación independiente
cuando el motor de aprobaciones de Cloud y la revisión independiente están
habilitados. Esto incluye aumentos, reducciones, cambios de tipo de tolerancia y
cambios que fortalecen controles. No hay clasificación entre debilitar y
fortalecer.

Guardar valores idénticos no crea una propuesta; los decimales numéricamente
iguales (por ejemplo, `5` y `5.0000`) son valores idénticos. Los cambios
pendientes no alteran la configuración activa. Otro revisor autorizado debe
aprobarlos, y una línea base cambiada impide aplicar una propuesta obsoleta. La
evidencia de auditoría conserva los valores antes/después, el actor y la
compañía.

Desktop conserva su operación de un solo usuario. La autorización de Cloud sigue
siendo obligatoria aunque el motor de aprobaciones esté deshabilitado. Los
snapshots históricos de matching permanecen sin cambios cuando cambia la
configuración activa.
