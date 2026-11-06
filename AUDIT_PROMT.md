# Procedimiento permanente de auditoría

La única fuente local de seguimiento de cobertura y avance es `AUDIT_MATRIX.csv`. GitHub Issues es la bitácora narrativa para hallazgos, investigaciones, pruebas, hipótesis y decisiones. La auditoría no autoriza correcciones de código ni cambios de reglas de negocio. Lee primero `AGENTS.md` y comprueba la rama y los cambios locales.

1. Consulta `AUDIT_MATRIX.csv` y selecciona una unidad `Pendiente` o `Parcial`.
2. Examina el código vigente, sus contratos, callers, validaciones, permisos, persistencia, errores y escenarios de riesgo aplicables. Consulta la evidencia existente y no repitas trabajo válido.
3. Antes de registrar un defecto, busca en GitHub Issues y añade la evidencia al issue correspondiente. Crea uno nuevo solo para un hallazgo verificable que no esté cubierto. No cambies el estado de un issue por el estado de cobertura.
4. Registra hallazgos, pruebas, hipótesis y decisiones en los issues; en la matriz escribe solo un comentario operativo breve y, cuando corresponda, la referencia al issue.
5. Actualiza únicamente las unidades revisadas: `Pendiente` si no hay evidencia individual suficiente; `Parcial` si hay revisión pero quedan brechas; `Completo` cuando el alcance aplicable esté cubierto. Un defecto abierto no impide `Completo`.
6. Revisa el contenido completo del archivo para identificar unidades añadidas, eliminadas o modificadas, y ejecuta el verificador. Investiga explícitamente las unidades que sus extractores no puedan analizar.
7. Continúa con la siguiente unidad pendiente o parcial. No agregues checkpoints, contadores manuales ni bitácoras narrativas locales.

## Cambios de código

Identifica las unidades afectadas y sus dependencias de contrato. Añade las nuevas como `Pendiente`, retira las eliminadas tras comprobarlas y reevalúa la cobertura de las modificadas. Conserva los estados de las unidades no afectadas. Una revisión anterior solo sigue siendo válida para código modificado después de comprobar el contrato y la evidencia pertinentes.

## Verificación y evidencia histórica

Ejecuta `.venv/bin/python scripts/check_audit_matrix.py --check-issues` para comprobar la estructura, contrastar las unidades que sus extractores reconocen, verificar las referencias a issues y obtener métricas derivadas. Un resultado correcto no prueba que los extractores identifiquen todo el código dinámico: revisa los marcadores de análisis pendiente y contrasta las unidades con el código real.

La evidencia anterior a la matriz permanece en Git. Por ejemplo, `git show 0f22aa10cf34c4d02e20a1e6ab9c551afce9c024:AUDIT_PROGRESS.md` permite consultarla; aplica el mismo procedimiento a los demás documentos históricos cuando sea necesario. Verifica que la evidencia corresponda a la implementación vigente antes de utilizarla.
