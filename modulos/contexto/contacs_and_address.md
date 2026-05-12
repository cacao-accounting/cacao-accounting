Implementation Requirement
Cacao Accounting — Party Contacts & Addresses Framework
1. 🎯 Objetivo

Diseñar un modelo de datos que permita a clientes y proveedores:

Tener múltiples contactos
Tener múltiples direcciones
Clasificar contactos y direcciones por propósito
Reutilizar contactos/direcciones entre entidades
Mantener consistencia y trazabilidad
2. 🧱 Principio Base

Contactos y direcciones NO pertenecen directamente a cliente/proveedor.

Son entidades independientes relacionadas mediante tablas de asociación.

3. 🧩 Modelo de Datos
3.1 Entidad: party
id
type (customer, supplier)
name
tax_id
3.2 Entidad: contact
id
first_name
last_name
email
phone
mobile
is_active
3.3 Entidad: address
id
address_line1
address_line2
city
state
country
postal_code
is_active
4. 🔗 Relaciones
4.1 Tabla: party_contact

Relación N

id
party_id
contact_id
role (ENUM)
Roles sugeridos:
billing
sales
purchasing
logistics
support
primary

📌 Permite:

múltiples contactos por rol
un contacto con múltiples roles
4.2 Tabla: party_address

Relación N

id
party_id
address_id
type (ENUM)
Tipos sugeridos:
billing
shipping
office
branch
warehouse
5. ⚙️ Reglas de Negocio (a nivel estructural)
5.1 Cardinalidad
Un party puede tener:
0..N contactos
0..N direcciones
5.2 Reutilización
Un contact puede pertenecer a múltiples party
Una address puede pertenecer a múltiples party
5.3 Contacto Primario

Debe existir capacidad para marcar:

contacto principal (is_primary o role=primary)
dirección principal
6. 🧠 Extensiones Futuras (debes anticiparlas)
6.1 Contactos por compañía

Tabla opcional futura:

company_party_contact

Permite:

roles distintos por compañía
visibilidad restringida
6.2 Versionado / Historial
cambios de dirección
contactos inactivos
6.3 Geolocalización

Campos futuros en address:

latitude
longitude
7. 🔒 Reglas de Integridad
No duplicar contactos innecesariamente
No eliminar contactos/direcciones en uso
Uso de is_active en lugar de delete
FK obligatorias
8. ⚠️ Anti-Patrones Prohibidos

❌ customer_contact como tabla separada
❌ duplicar dirección por cada cliente
❌ guardar dirección como texto plano en factura
❌ no permitir múltiples roles

9. 🔗 Relación con Transacciones

Tablas como:

sales_invoice
purchase_order

Deben poder referenciar:

contact_id
address_id

📌 Esto permite:

congelar datos en el momento de la transacción (snapshot en lógica futura)
10. 🚀 Criterio de Éxito

El sistema será exitoso si:

Soporta múltiples contactos/direcciones por entidad
Permite clasificación flexible
Evita duplicación de datos
Es extensible sin rediseño
