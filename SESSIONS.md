# Contexto de sesiones

Esta es una síntesis para continuidad. El historial completo, incluidas decisiones, verificaciones y referencias por issue, está preservado en Git:

```sh
git show fbef114431e603a89599c3c3c3de7e1a1cf5143e:SESSIONS.md
```

Consultar el historial por issue o tema antes de trabajar; sus estados y resultados son históricos, no prueba de que sigan vigentes. `AGENTS.md` contiene las reglas actuales de negocio y desarrollo; los issues son la bitácora de cada tarea.

- Controles Cloud: la aprobación de cuatro ojos exige usuario distinto, activo, autorizado y rango al menos igual al máximo de los preparadores; `approve` es requisito independiente. Un admin solo puede ser aprobado por otro admin. Ver historial y `docs/cloud/internal-controls.md` para excepciones y despliegue.
- La cadena de auditoría busca evidencia de alteración; las garantías ante acceso directo a BD dependen también de permisos de despliegue. Ver `audit_chain.py` y el historial antes de asumir su implementación o límites actuales.
- Concurrencia financiera #1653: se eligió lock y transición condicional; en SQLAlchemy `FOR UPDATE` puede requerir `populate_existing` para refrescar instancias ya cargadas. La alternativa de unique parcial y varios flujos hijos quedaron pendientes de criterio/revisión. Consultar #1653 y código actual.
- Para la auditoría activa, la cola y el punto de reanudación están en `AUDIT_PENDING.md`, `AUDIT_PROGRESS.md` y `AUDIT_PROMT.md`.
