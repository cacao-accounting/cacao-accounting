# Technical Debt Audit — cacao_accounting

Generated: 2026-05-10 04:03 UTC

---

# Summary

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 32 |
| Medium | 65 |
| Low | 23 |
| Info | 28 |

- Total Python files analyzed: **69**
- Total lines of code analyzed: **23641**
- Technical Debt Score: **51/100**

## Category distribution

- Maintainability: 79
- Typing: 30
- DevOps: 14
- Architecture: 10
- Flask: 6
- Performance: 6
- Security: 2
- ORM: 1

## Top files by estimated debt

- `cacao_accounting/compras/purchase_reconciliation_service.py` — debt_weight=28, issues=7, loc=1042
- `cacao_accounting/contabilidad/__init__.py` — debt_weight=28, issues=6, loc=1948
- `cacao_accounting/compras/__init__.py` — debt_weight=28, issues=6, loc=1256
- `cacao_accounting/ventas/__init__.py` — debt_weight=28, issues=6, loc=1004
- `cacao_accounting/bancos/__init__.py` — debt_weight=25, issues=6, loc=820
- `cacao_accounting/admin/__init__.py` — debt_weight=22, issues=7, loc=740
- `cacao_accounting/contabilidad/posting.py` — debt_weight=22, issues=6, loc=1840
- `cacao_accounting/inventario/__init__.py` — debt_weight=19, issues=6, loc=617
- `cacao_accounting/reportes/services.py` — debt_weight=19, issues=5, loc=1003
- `cacao_accounting/reportes/__init__.py` — debt_weight=19, issues=5, loc=844

## Top files by estimated complexity

- `cacao_accounting/contabilidad/posting.py` — complexity_index=374, loc=1840
- `cacao_accounting/contabilidad/__init__.py` — complexity_index=201, loc=1948
- `cacao_accounting/reportes/__init__.py` — complexity_index=201, loc=844
- `cacao_accounting/compras/__init__.py` — complexity_index=198, loc=1256
- `cacao_accounting/reportes/services.py` — complexity_index=176, loc=1003
- `cacao_accounting/ventas/__init__.py` — complexity_index=176, loc=1004
- `cacao_accounting/bancos/__init__.py` — complexity_index=160, loc=820
- `cacao_accounting/contabilidad/journal_service.py` — complexity_index=160, loc=623
- `cacao_accounting/admin/__init__.py` — complexity_index=142, loc=740
- `cacao_accounting/document_flow/service.py` — complexity_index=138, loc=670

---

# File: cacao_accounting/I18N.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/__init__.py

## MEDIUM — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: create_app (65 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): before_request, cleandb, error_400, error_403, error_404.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

## LOW — Security

### Issue

**Bandit B105:hardcoded_password_string**

Bandit reportó: Possible hardcoded password: 'test-secret-key'.

### Recommendation

Revisar el contexto y reemplazar valores sensibles hardcodeados por configuración segura en entorno.

---

## LOW — Security

### Issue

**Bandit B105:hardcoded_password_string**

Bandit reportó: Possible hardcoded password: 'dev-secret-key'.

### Recommendation

Revisar el contexto y reemplazar valores sensibles hardcodeados por configuración segura en entorno.

---

## LOW — DevOps

### Issue

**Uso de print en lugar de logging estructurado**

Se encontraron llamadas a `print`, lo cual dificulta trazabilidad en producción.

### Recommendation

Usar logger estructurado con contexto (módulo, request_id, usuario) y niveles adecuados.

---

# File: cacao_accounting/__main__.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/admin/__init__.py

## MEDIUM — Maintainability

### Issue

**Archivo extenso con alta carga cognitiva**

El archivo tiene 740 líneas; dificulta revisiones, pruebas y refactors seguros.

### Recommendation

Separar bloques funcionales en módulos más pequeños con límites de responsabilidad explícitos.

---

## HIGH — Flask

### Issue

**Controladores con acceso directo intensivo a base de datos**

Se detectaron 22 rutas y 60 operaciones directas con database.session en el mismo archivo.

### Recommendation

Mover consultas y persistencia a capa repository/service; dejar rutas como capa HTTP delgada.

---

## MEDIUM — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: rol_permisos (49 líneas); lista_modulos (48 líneas); cuentas_predeterminadas (48 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: crear_usuario (complejidad≈13); editar_usuario (complejidad≈13).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): admin_, config_conciliacion_compras, crear_rol, crear_usuario, cuentas_predeterminadas.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

## MEDIUM — Performance

### Issue

**Carga potencialmente masiva sin paginación visible**

Se detectó uso de `.all()` (17 veces) sin patrón explícito de paginación en el archivo.

### Recommendation

Aplicar paginación o límites de consulta en listados para evitar consumo excesivo de memoria.

---

## LOW — DevOps

### Issue

**Uso de print en lugar de logging estructurado**

Se encontraron llamadas a `print`, lo cual dificulta trazabilidad en producción.

### Recommendation

Usar logger estructurado con contexto (módulo, request_id, usuario) y niveles adecuados.

---

# File: cacao_accounting/admin/registros/__init__.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/api/__init__.py

## MEDIUM — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: document_flow_related_list (59 líneas); token_requerido (42 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): api_delivery_note_items, api_document_flow_close_document, api_document_flow_close_line, api_document_flow_create_target, api_document_flow_items.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

## LOW — DevOps

### Issue

**Uso de print en lugar de logging estructurado**

Se encontraron llamadas a `print`, lo cual dificulta trazabilidad en producción.

### Recommendation

Usar logger estructurado con contexto (módulo, request_id, usuario) y niveles adecuados.

---

# File: cacao_accounting/app/__init__.py

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): bd_actual, dev_info, informacion_para_desarrolladores, pagina_inicio, ping.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

## LOW — DevOps

### Issue

**Uso de print en lugar de logging estructurado**

Se encontraron llamadas a `print`, lo cual dificulta trazabilidad en producción.

### Recommendation

Usar logger estructurado con contexto (módulo, request_id, usuario) y niveles adecuados.

---

# File: cacao_accounting/auth/__init__.py

## MEDIUM — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: profile (79 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: profile (complejidad≈14).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): cargar_sesion, cerrar_sesion, inicio_sesion, no_autorizado, profile.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

## LOW — DevOps

### Issue

**Uso de print en lugar de logging estructurado**

Se encontraron llamadas a `print`, lo cual dificulta trazabilidad en producción.

### Recommendation

Usar logger estructurado con contexto (módulo, request_id, usuario) y niveles adecuados.

---

# File: cacao_accounting/auth/forms.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/auth/helpers.py

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): redireccion_despues_de_login.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

# File: cacao_accounting/auth/permisos.py

## HIGH — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: cargar_permisos_predeterminados (364 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

# File: cacao_accounting/auth/roles.py

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): obtener_roles_por_usuario.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

# File: cacao_accounting/bancos/__init__.py

## MEDIUM — Maintainability

### Issue

**Archivo extenso con alta carga cognitiva**

El archivo tiene 820 líneas; dificulta revisiones, pruebas y refactors seguros.

### Recommendation

Separar bloques funcionales en módulos más pequeños con límites de responsabilidad explícitos.

---

## HIGH — Flask

### Issue

**Controladores con acceso directo intensivo a base de datos**

Se detectaron 29 rutas y 49 operaciones directas con database.session en el mismo archivo.

### Recommendation

Mover consultas y persistencia a capa repository/service; dejar rutas como capa HTTP delgada.

---

## HIGH — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: bancos_pago_nuevo (112 líneas); bancos_transaccion_reconciliar (58 líneas); _crear_nota_bancaria (47 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## HIGH — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: bancos_pago_nuevo (complejidad≈38); _crear_nota_bancaria (complejidad≈17); bancos_transaccion_reconciliar (complejidad≈14).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): bancos_, bancos_banco, bancos_banco_lista, bancos_banco_nuevo, bancos_conciliacion_bancaria.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

## LOW — DevOps

### Issue

**Uso de print en lugar de logging estructurado**

Se encontraron llamadas a `print`, lo cual dificulta trazabilidad en producción.

### Recommendation

Usar logger estructurado con contexto (módulo, request_id, usuario) y niveles adecuados.

---

# File: cacao_accounting/bancos/forms.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/bancos/reconciliation_service.py

## HIGH — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: find_bank_reconciliation_candidates (83 líneas); reconcile_bank_items (72 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: reconcile_bank_items (complejidad≈13).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

# File: cacao_accounting/bancos/statement_service.py

## MEDIUM — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: create_bank_difference_journal (51 líneas); import_bank_statement (45 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: import_bank_statement (complejidad≈13).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

# File: cacao_accounting/cache.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/cli.py

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): linea_comandos.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

# File: cacao_accounting/compras/__init__.py

## HIGH — Architecture

### Issue

**Módulo monolítico de gran tamaño**

El archivo tiene 1256 líneas, lo que incrementa acoplamiento y costo de mantenimiento.

### Recommendation

Dividir por responsabilidades (routes/services/repositories/helpers) y mover casos de uso a servicios especializados.

---

## HIGH — Flask

### Issue

**Controladores con acceso directo intensivo a base de datos**

Se detectaron 40 rutas y 85 operaciones directas con database.session en el mismo archivo.

### Recommendation

Mover consultas y persistencia a capa repository/service; dejar rutas como capa HTTP delgada.

---

## HIGH — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: compras_factura_compra_nuevo (108 líneas); compras_recepcion_nuevo (74 líneas); compras_cotizacion_proveedor_nueva (63 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## HIGH — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: compras_factura_compra_nuevo (complejidad≈26); compras_cotizacion_proveedor_nueva (complejidad≈17); compras_recepcion_nuevo (complejidad≈16).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): compras_, compras_comparativo_ofertas, compras_comparativo_ofertas_lista, compras_cotizacion_proveedor, compras_cotizacion_proveedor_lista.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

## LOW — DevOps

### Issue

**Uso de print en lugar de logging estructurado**

Se encontraron llamadas a `print`, lo cual dificulta trazabilidad en producción.

### Recommendation

Usar logger estructurado con contexto (módulo, request_id, usuario) y niveles adecuados.

---

# File: cacao_accounting/compras/forms.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/compras/gr_ir_service.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/compras/purchase_reconciliation_service.py

## HIGH — Architecture

### Issue

**Módulo monolítico de gran tamaño**

El archivo tiene 1042 líneas, lo que incrementa acoplamiento y costo de mantenimiento.

### Recommendation

Dividir por responsabilidades (routes/services/repositories/helpers) y mover casos de uso a servicios especializados.

---

## HIGH — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: _reconcile_two_way (115 líneas); _reconcile_three_way (106 líneas); _finalize_reconciliation (56 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: _reconcile_three_way (complejidad≈14); _reconcile_two_way (complejidad≈14).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

## MEDIUM — Architecture

### Issue

**Firmas con exceso de parámetros**

Varias funciones reciben demasiados parámetros: _finalize_reconciliation (10 parámetros).

### Recommendation

Introducir dataclasses/DTOs para agrupar contratos y mejorar legibilidad/testabilidad.

---

## LOW — Typing

### Issue

**Uso frecuente de `Any`**

Se detectaron 18 referencias a `Any`, lo que reduce precisión de análisis estático.

### Recommendation

Reemplazar `Any` por tipos concretos, Protocols, TypedDict o genéricos parametrizados.

---

## MEDIUM — Performance

### Issue

**Carga potencialmente masiva sin paginación visible**

Se detectó uso de `.all()` (10 veces) sin patrón explícito de paginación en el archivo.

### Recommendation

Aplicar paginación o límites de consulta en listados para evitar consumo excesivo de memoria.

---

## HIGH — ORM

### Issue

**Patrón de query dentro de loop**

Se detectó al menos un patrón de consulta SQLAlchemy dentro de iteraciones, riesgo de N+1.

### Recommendation

Prefetch/bulk query fuera del loop y mapear en memoria para reducir round-trips a DB.

---

# File: cacao_accounting/config.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/contabilidad/__init__.py

## HIGH — Architecture

### Issue

**Módulo monolítico de gran tamaño**

El archivo tiene 1948 líneas, lo que incrementa acoplamiento y costo de mantenimiento.

### Recommendation

Dividir por responsabilidades (routes/services/repositories/helpers) y mover casos de uso a servicios especializados.

---

## HIGH — Flask

### Issue

**Controladores con acceso directo intensivo a base de datos**

Se detectaron 62 rutas y 110 operaciones directas con database.session en el mismo archivo.

### Recommendation

Mover consultas y persistencia a capa repository/service; dejar rutas como capa HTTP delgada.

---

## HIGH — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: ver_comprobante (124 líneas); naming_series_edit (62 líneas); naming_series_new (58 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## HIGH — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: ver_comprobante (complejidad≈30); naming_series_edit (complejidad≈14).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): accounting_period_delete, accounting_period_edit, accounting_period_new, activar_entidad, anular_comprobante.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

## LOW — DevOps

### Issue

**Uso de print en lugar de logging estructurado**

Se encontraron llamadas a `print`, lo cual dificulta trazabilidad en producción.

### Recommendation

Usar logger estructurado con contexto (módulo, request_id, usuario) y niveles adecuados.

---

# File: cacao_accounting/contabilidad/auxiliares.py

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): obtener_catalogo, obtener_catalogo_base, obtener_catalogo_centros_costo_base, obtener_centros_costos, obtener_entidad.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

## MEDIUM — Performance

### Issue

**Carga potencialmente masiva sin paginación visible**

Se detectó uso de `.all()` (11 veces) sin patrón explícito de paginación en el archivo.

### Recommendation

Aplicar paginación o límites de consulta en listados para evitar consumo excesivo de memoria.

---

# File: cacao_accounting/contabilidad/ctas/__init__.py

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): cargar_catalogos.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

# File: cacao_accounting/contabilidad/default_accounts.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/contabilidad/forms.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/contabilidad/gl/__init__.py

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): gl_list, gl_new.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

## LOW — DevOps

### Issue

**Uso de print en lugar de logging estructurado**

Se encontraron llamadas a `print`, lo cual dificulta trazabilidad en producción.

### Recommendation

Usar logger estructurado con contexto (módulo, request_id, usuario) y niveles adecuados.

---

# File: cacao_accounting/contabilidad/journal_repository.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/contabilidad/journal_service.py

## MEDIUM — Maintainability

### Issue

**Archivo extenso con alta carga cognitiva**

El archivo tiene 623 líneas; dificulta revisiones, pruebas y refactors seguros.

### Recommendation

Separar bloques funcionales en módulos más pequeños con límites de responsabilidad explícitos.

---

## HIGH — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: _serialize_journal_line (complejidad≈19); _validate_balanced_lines (complejidad≈13).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

## LOW — Typing

### Issue

**Uso frecuente de `Any`**

Se detectaron 20 referencias a `Any`, lo que reduce precisión de análisis estático.

### Recommendation

Reemplazar `Any` por tipos concretos, Protocols, TypedDict o genéricos parametrizados.

---

# File: cacao_accounting/contabilidad/posting.py

## HIGH — Architecture

### Issue

**Módulo monolítico de gran tamaño**

El archivo tiene 1840 líneas, lo que incrementa acoplamiento y costo de mantenimiento.

### Recommendation

Dividir por responsabilidades (routes/services/repositories/helpers) y mover casos de uso a servicios especializados.

---

## HIGH — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: post_purchase_invoice (97 líneas); cancel_document (97 líneas); post_payment_entry (96 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: _create_stock_ledger (complejidad≈18); post_payment_entry (complejidad≈16); post_purchase_invoice (complejidad≈15).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

## MEDIUM — Architecture

### Issue

**Firmas con exceso de parámetros**

Varias funciones reciben demasiados parámetros: _create_gl_entry (16 parámetros).

### Recommendation

Introducir dataclasses/DTOs para agrupar contratos y mejorar legibilidad/testabilidad.

---

## LOW — Typing

### Issue

**Uso frecuente de `Any`**

Se detectaron 34 referencias a `Any`, lo que reduce precisión de análisis estático.

### Recommendation

Reemplazar `Any` por tipos concretos, Protocols, TypedDict o genéricos parametrizados.

---

## MEDIUM — Performance

### Issue

**Carga potencialmente masiva sin paginación visible**

Se detectó uso de `.all()` (11 veces) sin patrón explícito de paginación en el archivo.

### Recommendation

Aplicar paginación o límites de consulta en listados para evitar consumo excesivo de memoria.

---

# File: cacao_accounting/database/__init__.py

## HIGH — Architecture

### Issue

**Módulo monolítico de gran tamaño**

El archivo tiene 2235 líneas, lo que incrementa acoplamiento y costo de mantenimiento.

### Recommendation

Dividir por responsabilidades (routes/services/repositories/helpers) y mover casos de uso a servicios especializados.

---

# File: cacao_accounting/database/helpers.py

## MEDIUM — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: generate_identifier (67 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): db_version, entidades_creadas, usuarios_creados, verifica_coneccion_db.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

## MEDIUM — Maintainability

### Issue

**Captura amplia de `Exception`**

Se detectaron 2 capturas genéricas de Exception.

### Recommendation

Refinar captura por tipos de error esperados y mantener manejo diferenciado por contexto.

---

# File: cacao_accounting/datos/__init__.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/datos/base/__init__.py

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): base_data, crea_usuario_admin, registra_monedas.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

# File: cacao_accounting/datos/base/data.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/datos/dev/__init__.py

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): asignar_usuario_a_roles, cargar_articulos, cargar_bancos, cargar_bodegas, cargar_catalogo_de_cuentas.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

# File: cacao_accounting/datos/dev/data.py

## MEDIUM — Maintainability

### Issue

**Archivo extenso con alta carga cognitiva**

El archivo tiene 621 líneas; dificulta revisiones, pruebas y refactors seguros.

### Recommendation

Separar bloques funcionales en módulos más pequeños con límites de responsabilidad explícitos.

---

## HIGH — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: _make_centros_de_costos (99 líneas); _make_cuentas (66 líneas); _make_documentos (62 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

# File: cacao_accounting/decorators.py

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): decorator_modulo_activo, decorator_verifica_acceso, modulo_activo, verifica_acceso, wrapper.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

# File: cacao_accounting/document_flow/__init__.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/document_flow/registry.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/document_flow/repository.py

## MEDIUM — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: recompute_line_flow_state (42 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

# File: cacao_accounting/document_flow/service.py

## MEDIUM — Maintainability

### Issue

**Archivo extenso con alta carga cognitiva**

El archivo tiene 670 líneas; dificulta revisiones, pruebas y refactors seguros.

### Recommendation

Separar bloques funcionales en módulos más pequeños con límites de responsabilidad explícitos.

---

## HIGH — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: create_target_document (87 líneas); _create_payment_target (58 líneas); create_document_relation (57 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: create_target_document (complejidad≈15); _create_payment_target (complejidad≈15); apply_advance_to_invoice (complejidad≈14).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

## MEDIUM — Architecture

### Issue

**Firmas con exceso de parámetros**

Varias funciones reciben demasiados parámetros: create_document_relation (10 parámetros).

### Recommendation

Introducir dataclasses/DTOs para agrupar contratos y mejorar legibilidad/testabilidad.

---

## LOW — Typing

### Issue

**Uso frecuente de `Any`**

Se detectaron 28 referencias a `Any`, lo que reduce precisión de análisis estático.

### Recommendation

Reemplazar `Any` por tipos concretos, Protocols, TypedDict o genéricos parametrizados.

---

# File: cacao_accounting/document_flow/status.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/document_flow/tracing.py

## MEDIUM — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: _build_groups (57 líneas); document_flow_summary (46 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Performance

### Issue

**Carga potencialmente masiva sin paginación visible**

Se detectó uso de `.all()` (4 veces) sin patrón explícito de paginación en el archivo.

### Recommendation

Aplicar paginación o límites de consulta en listados para evitar consumo excesivo de memoria.

---

# File: cacao_accounting/document_identifiers.py

## MEDIUM — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: assign_document_identifier (76 líneas); _resolve_external_counter (73 líneas); _validate_and_register_external_number (48 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: _resolve_external_counter (complejidad≈15); _pick_naming_series (complejidad≈14).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

# File: cacao_accounting/exceptions/__init__.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/exceptions/mensajes.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/form_preferences.py

## LOW — Typing

### Issue

**Uso frecuente de `Any`**

Se detectaron 9 referencias a `Any`, lo que reduce precisión de análisis estático.

### Recommendation

Reemplazar `Any` por tipos concretos, Protocols, TypedDict o genéricos parametrizados.

---

# File: cacao_accounting/gl/__init__.py

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): agregar_entrada, remover_entrada.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

# File: cacao_accounting/inventario/__init__.py

## MEDIUM — Maintainability

### Issue

**Archivo extenso con alta carga cognitiva**

El archivo tiene 617 líneas; dificulta revisiones, pruebas y refactors seguros.

### Recommendation

Separar bloques funcionales en módulos más pequeños con límites de responsabilidad explícitos.

---

## HIGH — Flask

### Issue

**Controladores con acceso directo intensivo a base de datos**

Se detectaron 35 rutas y 25 operaciones directas con database.session en el mismo archivo.

### Recommendation

Mover consultas y persistencia a capa repository/service; dejar rutas como capa HTTP delgada.

---

## MEDIUM — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: inventario_entrada_nuevo (60 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: inventario_entrada_nuevo (complejidad≈16).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): inventario_, inventario_ajuste_lista, inventario_ajuste_negativo_lista, inventario_ajuste_negativo_nuevo, inventario_ajuste_nuevo.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

## LOW — DevOps

### Issue

**Uso de print en lugar de logging estructurado**

Se encontraron llamadas a `print`, lo cual dificulta trazabilidad en producción.

### Recommendation

Usar logger estructurado con contexto (módulo, request_id, usuario) y niveles adecuados.

---

# File: cacao_accounting/inventario/forms.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/inventario/service.py

## MEDIUM — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: validate_batch_serial (complejidad≈14).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

# File: cacao_accounting/logs.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/modulos/__init__.py

## LOW — DevOps

### Issue

**Uso de print en lugar de logging estructurado**

Se encontraron llamadas a `print`, lo cual dificulta trazabilidad en producción.

### Recommendation

Usar logger estructurado con contexto (módulo, request_id, usuario) y niveles adecuados.

---

# File: cacao_accounting/reportes/__init__.py

## MEDIUM — Maintainability

### Issue

**Archivo extenso con alta carga cognitiva**

El archivo tiene 844 líneas; dificulta revisiones, pruebas y refactors seguros.

### Recommendation

Separar bloques funcionales en módulos más pequeños con límites de responsabilidad explícitos.

---

## HIGH — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: _render_financial_report (94 líneas); _export_financial_report (65 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## HIGH — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: _restore_filters_from_view (complejidad≈33); _render_financial_report (complejidad≈29); _export_financial_report (complejidad≈16).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): account_movement, aging, balance_sheet, batches, gross_margin.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

## LOW — DevOps

### Issue

**Uso de print en lugar de logging estructurado**

Se encontraron llamadas a `print`, lo cual dificulta trazabilidad en producción.

### Recommendation

Usar logger estructurado con contexto (módulo, request_id, usuario) y niveles adecuados.

---

# File: cacao_accounting/reportes/services.py

## HIGH — Architecture

### Issue

**Módulo monolítico de gran tamaño**

El archivo tiene 1003 líneas, lo que incrementa acoplamiento y costo de mantenimiento.

### Recommendation

Dividir por responsabilidades (routes/services/repositories/helpers) y mover casos de uso a servicios especializados.

---

## HIGH — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: get_income_statement_report (97 líneas); get_balance_sheet_report (86 líneas); get_account_movement_detail (85 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: get_account_movement_detail (complejidad≈16); _apply_gl_filters (complejidad≈15); get_trial_balance_report (complejidad≈14).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

## LOW — Typing

### Issue

**Uso frecuente de `Any`**

Se detectaron 10 referencias a `Any`, lo que reduce precisión de análisis estático.

### Recommendation

Reemplazar `Any` por tipos concretos, Protocols, TypedDict o genéricos parametrizados.

---

## MEDIUM — Performance

### Issue

**Carga potencialmente masiva sin paginación visible**

Se detectó uso de `.all()` (8 veces) sin patrón explícito de paginación en el archivo.

### Recommendation

Aplicar paginación o límites de consulta en listados para evitar consumo excesivo de memoria.

---

# File: cacao_accounting/search_select.py

## LOW — Typing

### Issue

**Uso frecuente de `Any`**

Se detectaron 21 referencias a `Any`, lo que reduce precisión de análisis estático.

### Recommendation

Reemplazar `Any` por tipos concretos, Protocols, TypedDict o genéricos parametrizados.

---

# File: cacao_accounting/server.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/setup/__init__.py

## MEDIUM — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: setup (75 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: setup (complejidad≈15).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): setup.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

## LOW — DevOps

### Issue

**Uso de print en lugar de logging estructurado**

Se encontraron llamadas a `print`, lo cual dificulta trazabilidad en producción.

### Recommendation

Usar logger estructurado con contexto (módulo, request_id, usuario) y niveles adecuados.

---

# File: cacao_accounting/setup/forms.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/setup/repository.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/setup/service.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/tax_pricing_service.py

## MEDIUM — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: calculate_taxes (63 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## MEDIUM — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: calculate_taxes (complejidad≈15).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

# File: cacao_accounting/validaciones/__init__.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/ventas/__init__.py

## HIGH — Architecture

### Issue

**Módulo monolítico de gran tamaño**

El archivo tiene 1004 líneas, lo que incrementa acoplamiento y costo de mantenimiento.

### Recommendation

Dividir por responsabilidades (routes/services/repositories/helpers) y mover casos de uso a servicios especializados.

---

## HIGH — Flask

### Issue

**Controladores con acceso directo intensivo a base de datos**

Se detectaron 32 rutas y 75 operaciones directas con database.session en el mismo archivo.

### Recommendation

Mover consultas y persistencia a capa repository/service; dejar rutas como capa HTTP delgada.

---

## HIGH — Maintainability

### Issue

**Funciones largas que concentran demasiada lógica**

Se detectaron funciones por encima del umbral recomendado: ventas_factura_venta_nuevo (105 líneas); ventas_entrega_nuevo (74 líneas); ventas_orden_venta_nuevo (67 líneas).

### Recommendation

Aplicar extracción de funciones y composición por pasos para reducir tamaño y facilitar pruebas unitarias.

---

## HIGH — Maintainability

### Issue

**Complejidad ciclomática elevada**

Se identificaron funciones con múltiples ramas y caminos de ejecución: ventas_factura_venta_nuevo (complejidad≈27); ventas_orden_venta_nuevo (complejidad≈19); ventas_cotizacion_nueva (complejidad≈17).

### Recommendation

Separar decisiones por estrategia o funciones auxiliares y reducir anidación condicional.

---

## MEDIUM — Typing

### Issue

**Cobertura incompleta de type hints en funciones públicas**

Funciones públicas con anotaciones incompletas detectadas (ejemplos): ventas_, ventas_cliente, ventas_cliente_lista, ventas_cliente_nuevo, ventas_cotizacion.

### Recommendation

Añadir type hints de parámetros y retorno en API pública para mejorar contratos y prevenir errores en runtime.

---

## LOW — DevOps

### Issue

**Uso de print en lugar de logging estructurado**

Se encontraron llamadas a `print`, lo cual dificulta trazabilidad en producción.

### Recommendation

Usar logger estructurado con contexto (módulo, request_id, usuario) y niveles adecuados.

---

# File: cacao_accounting/ventas/forms.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

# File: cacao_accounting/version/__init__.py

## INFO — Maintainability

### Issue

**Sin hallazgos priorizados por heurística**

No se detectaron problemas relevantes con las reglas automáticas configuradas para este archivo.

### Recommendation

Mantener cobertura de pruebas y revisar periódicamente con auditoría manual en cambios complejos.

---

