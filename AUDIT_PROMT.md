# Instrucción para retomar la auditoría

La auditoría está pausada; reanudar cuando lo solicite el usuario. Objetivo: auditar archivo por archivo, clase por clase y función por función todo el código productivo y ejecutable de Cacao Accounting, incluyendo Python, Jinja/HTML, Alpine/JS, SQL, migraciones y configuración con comportamiento. No reiniciar ni darla por terminada hasta verificar todo el alcance.

## Antes de continuar

1. Leer `AGENTS.md`, `AUDIT_PROGRESS.md` y las filas pertinentes de `AUDIT_PENDING.md`; consultar `SESSIONS.md` cuando corresponda. El historial completo de ambos documentos sintetizados está en Git en `fbef114431e603a89599c3c3c3de7e1a1cf5143e`; los comandos de consulta están en cada archivo.
2. Comprobar rama, HEAD y cambios locales. Referencia: `estabilizacion`, código auditado en `73fcbd3feab0f7c56bdbd082c4b7422a41ce473f`, seguimiento consolidado en `fbef114431e603a89599c3c3c3de7e1a1cf5143e`. Comparar cambios y hashes; invalidar solo cobertura afectada y sus dependencias. Preservar trabajo ajeno.
3. Reconciliar rutas únicas con el inventario real. Referencia al consolidar: 557 rutas, 84 completas, 473 pendientes de cierre (287 parciales, 186 pendientes), 0 deltas y 2 criterios (#1888/#1889). Estos valores no prueban cobertura y deben recalcularse. El manifiesto histórico tiene 577 filas para 557 rutas únicas; no contar duplicados.

## Continuación

El componente activo es Persistencia, subflujo Inventario/StockEntry. Seguir la secuencia y referencias de `AUDIT_PROGRESS.md`: completar cancelación/reversa y límites no acreditados, importes sin moneda en listado, superficies y escritores restantes de StockEntry, y después modelos/DDL/consumidores de `database/__init__.py` y `database/helpers.py`. #1868 ya tiene reproducción PostgreSQL con dos sesiones; falta integración completa, no volver a tratarlo como hipótesis sin reproducción. Consultar evidencia histórica e issues antes de repetir trabajo.

Mantener un módulo y flujo activo a la vez. Coordinar un agente para Python y otro para plantillas/JS del mismo flujo, como solicitó el usuario; cotejar payload, validaciones, persistencia, ledger y presentación. Revisar las dependencias transversales solo hasta el contrato necesario, sin declararlas completas. Las plantillas contienen lógica de negocio y requieren revisión completa.

## Método y seguimiento

Revisar todas las ramas relevantes, permisos, errores y transiciones; cuando corresponda, aislamiento por compañía, libros/monedas, append-only, reversas, concurrencia, atomicidad e idempotencia. Comprobar frontend y autorización del servidor. Leer un archivo o contar símbolos no acredita cobertura funcional.

Antes de crear o ampliar issues, consultar estado y contenido actuales, buscar duplicados y confirmar evidencia, resultado esperado/observado, impacto y límites. Mantener candidatos sin confirmar como tales; usar `Refs: #NNN`. Registrar en `AUDIT_PROGRESS.md` símbolos, contratos, hashes, evidencia y límites; mantener `AUDIT_PENDING.md` únicamente con rutas sin cierre y retirar una fila solo al cubrir todo su alcance. Al cerrar un componente, documentar superficies, casos límite, issues y pendientes.

Auditoría de solo lectura sobre producto: no modificar código, tests, workflows ni decisiones de negocio. Los documentos de seguimiento se actualizan para continuidad. No ejecutar la suite completa por rutina; usar comprobaciones necesarias para validar hallazgos y distinguir sondas manuales de tests. No hacer commit ni push sin autorización. No declarar completa la auditoría mientras quede cobertura requerida sin verificar.
