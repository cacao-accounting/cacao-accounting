# Issues bloqueados por trabajo de terceros

Actualizado: 2026-11-22 (HEAD `7c92928f`).

Este documento identifica los issues que **no pueden completarse dentro de este
repositorio** porque dependen de trabajo, decisiones o infraestructura que
corresponde a otra persona, equipo o sistema. Se mantienen en `needs-work` hasta
que la dependencia se resuelva; no se marcan `fix-proposed` ni `fixed` sin la
evidencia que cada uno exige.

## 1. Evidencia Tier 1 en PostgreSQL

| Issue | Qué falta | Dependencia |
|---|---|---|
| #1767 | Bloqueo determinista del último administrador y carrera multi-sesión | Ejecutar la regresión contra un PostgreSQL de pruebas estable |
| #1731 | `db_version` con URI sin driver | Validación con motor real; el fix de detección debe probarse contra PostgreSQL |
| #1738 | Comparaciones de bloqueo horario con zona horaria en PostgreSQL | Motor real con zona configurada |
| #2209 / #2131 | Hallazgo de concurrencia del paraguas | Motor real |
| Fase 2 (#1653 y lotes por consumidor) | Tests de idempotencia/atomicidad multi-sesión (#1093, #1094, #1139, #1177, #1178, #1266, #1271, #1306, #1689, #2082, #2084, #2128, #2129, #2138, #2186, #2187, #2188) | PostgreSQL Tier 1 disponible y estable para CI y local |

Estado actual de la dependencia: existe una base de desarrollo en Neon
(`postgresql.txt`, PostgreSQL 17.12, base `cacao`). Está disponible para
validaciones puntuales, pero **no** como motor de CI ni para ejecutar la suite
completa: las pruebas crean y recrean esquema y agotan el tiempo del turno.
Mientras no exista una instancia dedicada, estos issues no pueden cerrarse con
la evidencia que exige `AGENTS.md`.

## 2. Decisiones de producto

| Issue | Decisión requerida |
|---|---|
| #1340 | Alcance (compañía/dimensión/global) y precedencia de valores dimensionales |
| #2169 | Centro de costo demo predeterminado (código, nombre y compañía) |
| #1848 | Bootstrap: ¿reanudación idempotente de `base_data` o fallo cerrado ante base parcial? |
| #759 | Diario en borrador y valoración de inventario pendientes de definición |
| #1318 | Estrategia de datos para contexto de conciliación heredado (hoy el backfill no existe y los consumidores usan fallbacks) |

Estas decisiones cambian reglas de negocio o el arranque de Desktop/Cloud; no
corresponde al agente implementador adoptarlas por iniciativa propia.

## 3. Refactor de esquema con migración

| Issue | Qué falta | Por qué no es un cambio local |
|---|---|---|
| #1681 | Unicidad de `code` por `(entity, code)` en `Unit`, `Book` y `Project` | Quitar el índice único global rompe las FK que apuntan a `book.code` (`import_batch` y otras): SQLite exige unicidad en la clave padre. Requiere reconstruir tablas/FK y resolver detalle por código+compañía |
| #1687 | Evitar tarifas duplicadas por nivel de precio | Requiere definir el tratamiento de NULL (`uom`, `min_qty`, `valid_from`) en la clave única y deduplicar datos existentes |
| #1987, #1683, #1697 | Vínculo append-only y columnas muertas con migración efectiva | Dependen del contrato de migraciones sobre bases con datos (ADR #1898) |

## 4. Trabajo paralelo en el árbol

Durante esta sesión otro proceso modificó y commiteó archivos del repositorio
(`inventario/service.py`, `messages.po`, `tests/conftest.py`, entre otros). El
agente implementador **no revierte, no reorganiza ni commitea** trabajo ajeno.
Cuando un issue toque un archivo con cambios de terceros sin commitear, se
coordina antes de intervenir; por eso #1731 quedó sin commit pese a tener el
cambio identificado.

## Cómo desbloquear

1. **PostgreSQL dedicado** (o `CHECK_DATABASE=true` con una base desechable por
   ejecución) para los issues de Tier 1.
2. Respuestas a las decisiones de la sección 2.
3. Aprobación explícita del refactor de claves de la sección 3, con su
   migración y verificación de datos.
