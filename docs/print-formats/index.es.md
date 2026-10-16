# Servicio de Impresión en Cacao Accounting

El Servicio de Impresión es un componente reutilizable diseñado para generar documentos HTML y PDF consistentes, profesionales y seguros para todas las transacciones del sistema.

## Para Administradores

Los administradores pueden gestionar los formatos de impresión de forma global o por compañía.

- **Gestión Centralizada**: Crear, editar y duplicar templates desde una única interfaz.
- **Templates de Sistema**: Cada transacción incluye un template de sistema estándar no editable que puede utilizarse como punto de partida.
- **Versionado**: Cada cambio a un template se guarda como una nueva versión, lo que permite su revisión histórica y restauración.
- **Seguridad**: Los templates se renderizan en un entorno sandbox seguro para prevenir la ejecución de código malicioso.

## Conceptos Clave

### Template vs. Hoja de Estilos
Un formato de impresión consta de dos partes:
1. **Cuerpo del Template**: La estructura HTML que usa la sintaxis de Jinja2 para datos dinámicos.
2. **Cuerpo de la Hoja de Estilos**: Reglas CSS para controlar el diseño y la apariencia.

### Sin Snapshots
Cacao Accounting **no** almacena snapshots de los PDF o HTML generados. Los documentos siempre se renderizan utilizando los datos actuales en la base de datos y la última versión publicada del template seleccionado.

### Validación por QR
Los documentos pueden incluir un código QR que permite a terceros verificar la autenticidad e integridad del documento escaneándolo.
