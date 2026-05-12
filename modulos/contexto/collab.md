Implementation Requirement
Cacao Accounting — Collaboration, Workflow & Attachments Framework
1. 🎯 Objetivo

Diseñar un conjunto de estructuras de datos que soporten:

Comentarios y menciones (@)
Asignaciones de registros
Flujos de aprobación multiusuario
Gestión de archivos adjuntos

Todo esto debe:

Funcionar en modo cloud (multiusuario)
Ser opcional en modo desktop (monousuario)
Estar desacoplado del dominio contable
Ser aplicable a cualquier entidad del sistema
2. ⚙️ Modo de Operación
2.1 Flag del sistema
DESKTOP_MODE (boolean)
2.2 Reglas
En modo desktop:
Todas las tablas existen
Funcionalidades pueden estar desactivadas a nivel aplicación
En modo cloud:
Funcionalidades completas habilitadas

📌 Importante:

El modelo de datos es único; el comportamiento cambia, no la estructura

3. 🧱 Patrón Base (Universal Linking)

Todas las entidades transversales deben usar:

reference_type (string)
reference_id (FK lógica)

📌 Esto permite asociar:

comentarios
archivos
asignaciones
aprobaciones

a cualquier tabla del sistema

4. 💬 Comentarios y Menciones
4.1 Tabla: comment
id
reference_type
reference_id
content (text)
created_by
created_at
4.2 Tabla: comment_mention
id
comment_id
user_id
4.3 Reglas
Un comentario puede tener múltiples menciones
No duplicar menciones
No eliminar comentarios → usar soft delete si aplica
5. 📌 Asignaciones
5.1 Tabla: assignment
id
reference_type
reference_id
assigned_to (user_id)
assigned_by
status (open, in_progress, completed, cancelled)
due_date
created_at
5.2 Reglas
Un registro puede tener múltiples asignaciones
Debe existir historial (no overwrite)
6. 🔄 Workflow / Aprobaciones
6.1 Modelo Base
workflow
id
name
entity_type
is_active
workflow_state
id
workflow_id
name
is_initial
is_final
workflow_transition
id
from_state_id
to_state_id
action_name
role_required
6.2 Instancia por registro
workflow_instance
id
workflow_id
reference_type
reference_id
current_state_id
workflow_action_log
id
workflow_instance_id
action
performed_by
performed_at
from_state
to_state
6.3 Reglas
Cada documento puede tener 0 o 1 workflow activo
Estados deben ser trazables
No eliminar historial
7. 📎 Archivos Adjuntos
7.1 Tabla: file
id
file_name
file_path / blob_reference
file_size
mime_type
uploaded_by
created_at
7.2 Tabla: file_attachment
id
file_id
reference_type
reference_id
7.3 Reglas
Un archivo puede asociarse a múltiples registros
No eliminar archivos en uso
Soportar almacenamiento externo (S3, local, etc.)
8. 👤 Usuarios y Roles (mínimo necesario)
8.1 Tabla: user
id
email
name
is_active
8.2 Tabla: role
id
name
8.3 Tabla: user_role
id
user_id
role_id

📌 Necesario para:

menciones
asignaciones
workflows
9. 🔒 Reglas de Integridad
reference_type + reference_id deben ser válidos (validación lógica)
Índices obligatorios:
(reference_type, reference_id)
No eliminación física en tablas críticas
Auditoría compatible con audit_log
10. ⚠️ Anti-Patrones Prohibidos

❌ Tabla de comentarios por cada módulo
❌ FK rígidas a cada tabla
❌ Duplicar archivos
❌ Workflow embebido en documentos
❌ Lógica de permisos en DB (solo estructura)

11. 🧠 Extensibilidad

Este diseño permite agregar:

Notificaciones
Actividad tipo “timeline”
Chat por documento
Integraciones externas
12. 🚀 Criterio de Éxito

El sistema será exitoso si:

Permite colaboración multiusuario sin rediseño
Funciona sin fricción en modo desktop
Escala a múltiples entidades sin duplicación
Mantiene trazabilidad completa
