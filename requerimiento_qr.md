# Requerimiento de implementación

# Validación externa de documentos impresos mediante QR

## Objetivo

Implementar una funcionalidad complementaria al servicio reusable de impresión de Cacao Accounting que permita validar públicamente documentos impresos mediante un código QR.

La funcionalidad debe permitir que un tercero confirme que:

* El documento fue emitido por Cacao Accounting.
* El documento corresponde a un registro existente en el sistema.
* Los datos principales del documento coinciden con el registro actual.
* El documento no aparenta haber sido alterado.
* El documento mantiene un estado válido, anulado, revertido o cancelado.

La funcionalidad debe integrarse con el sistema de formatos de impresión existente y respetar la arquitectura definida del servicio reusable de impresión.

---

## Alcance

La implementación debe incluir:

* Configuración global para habilitar/deshabilitar validación pública.
* Configuración global de URL pública de validación.
* Generación de token público seguro para documentos compartibles con terceros.
* Integración con el servicio de posting.
* Generación de hash de validación.
* Integración con context builders del servicio de impresión.
* Inclusión condicional del QR en todos los formatos predeterminados del sistema.
* Endpoint público de validación.
* Actualización de documentación en `docs/print-formats/`.
* Tests unitarios, funcionales y de seguridad.

---

## Configuración global

Agregar configuración global:

### `external_document_validation_enabled`

Tipo:

```text
boolean
```

Propósito:

Habilitar o deshabilitar la validación pública de documentos.

Reglas:

* Si es `false`, el sistema no debe mostrar QR.
* Si es `false`, el endpoint público debe responder “validación no disponible”.
* Si es `true`, el sistema puede generar QR para documentos aplicables.

---

### `external_document_validation_base_url`

Tipo:

```text
string
```

Propósito:

Definir la URL pública utilizada para validación externa.

Ejemplos válidos:

```text
https://miempresa.com
https://docs.miempresa.com
https://cacaocontent.com
```

Valor por defecto:

```text
https://cacaocontent.com
```

Reglas:

* Si está vacío, usar `https://cacaocontent.com`.
* Debe ser configurable por administrador.
* Debe utilizarse para construir URLs públicas de validación.

La URL final debe seguir este formato:

```text
<external_document_validation_base_url>/public/validate_doc/<token>
```

---

## Documentos sujetos a validación externa

El sistema debe generar validación pública para documentos susceptibles de compartirse con terceros.

Como mínimo:

```text
Factura de venta
Nota de crédito de venta
Nota de débito de venta
Recibo de caja
Comprobante de pago
Orden de compra
Cotización
Comprobante contable
Comprobante de revaluación
Movimientos de inventario compartibles
```

El sistema debe permitir ampliar esta lista.

---

## Modelo transversal de validación pública

Implementar modelo:

```python
class PublicDocumentValidation(db.Model):
    __tablename__ = "public_document_validations"

    id = db.Column(db.Integer, primary_key=True)

    public_token = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False,
    )

    document_type = db.Column(db.String(80), nullable=False)
    document_id = db.Column(db.Integer, nullable=False)

    document_number = db.Column(db.String(80), nullable=False)
    document_date = db.Column(db.Date, nullable=True)
    document_status = db.Column(db.String(40), nullable=False)

    validation_hash = db.Column(
        db.String(128),
        nullable=False,
    )

    is_enabled = db.Column(
        db.Boolean,
        default=True,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
    )
```

### Reglas

* No usar IDs internos como identificador público.
* No usar IDs secuenciales.
* El token debe ser único.
* El token debe ser no predecible.
* El token debe persistir para el documento.
* El token debe reutilizarse en reimpresiones.

La generación debe utilizar la dependencia ya existente en el repositorio o `secrets.token_urlsafe()`.

---

## Actualización del posting service

Actualizar el servicio de posting.

Cuando un documento sujeto a compartirse con terceros alcance un estado oficial/posteado/emitido:

El sistema debe:

1. Verificar si ya existe token.
2. Crear token si no existe.
3. Generar hash de validación.
4. Persistir información en `PublicDocumentValidation`.

### Reglas

No generar token para:

```text
draft
borradores
documentos no oficiales
```

Si el documento ya tiene token:

```text
No regenerarlo automáticamente
```

Si el documento cambia mediante un flujo permitido:

Actualizar:

* `validation_hash`
* `document_status`
* `document_date`
* `updated_at`

Si el documento se anula, revierte o cancela:

* Mantener el token.
* Actualizar hash.
* Actualizar estado.

---

## Hash de validación

El sistema debe generar un hash basado en un payload canónico.

Campos sugeridos:

```text
company_id
company_tax_id
document_type
document_id
document_number
document_date
currency
total/grand_total
status
customer/vendor tax_id
line_count
```

No incluir:

```text
printed_at
printed_by
notas internas
cuentas contables
centros de costo
proyectos
costos internos
datos bancarios sensibles
```

El hash debe generarse usando:

```python
canonical_payload = json.dumps(
    payload,
    sort_keys=True,
    separators=(",", ":")
)

validation_hash = hashlib.sha256(
    canonical_payload.encode("utf-8")
).hexdigest()
```

### Reglas

* Debe usar JSON canónico.
* Debe ser determinístico.
* Debe recalcularse desde el documento actual.
* Debe evitar campos volátiles.
* Debe evitar datos sensibles.

---

## Integración con context builders

Todos los documentos validables deben exponer:

```python
"validation": {
    "enabled": True,
    "public_url": "<url>",
    "qr_data_uri": "<base64 qr>",
    "token": "<token>"
}
```

Ejemplo:

```python
{
    "validation": {
        "enabled": True,
        "public_url": "https://cacaocontent.com/public/validate_doc/abc123",
        "qr_data_uri": "data:image/png;base64,...",
        "token": "abc123",
    }
}
```

Si la validación está deshabilitada:

```python
{
    "validation": {
        "enabled": False,
        "public_url": None,
        "qr_data_uri": None,
        "token": None,
    }
}
```

### Reglas

* El template nunca construye URLs.
* El template solo consume `validation`.
* El QR debe generarse como `data URI`.
* La solución debe funcionar con WeasyPrint sin requests adicionales.

---

## Actualización de plantillas predeterminadas

Todos los formatos predeterminados del sistema deben incluir soporte para QR condicional.

Agregar bloque estándar:

```jinja2
{% if validation.enabled and validation.qr_data_uri %}
<div class="validation-block">
    <img
        src="{{ validation.qr_data_uri }}"
        class="qr-code"
        alt="Document validation QR"
    >

    <div class="validation-text">
        <strong>Validate document</strong><br>
        Scan this QR code to verify this document.
    </div>
</div>
{% endif %}
```

CSS base:

```css
.validation-block {
    margin-top: 16px;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 10px;
    color: #374151;
}

.qr-code {
    width: 72px;
    height: 72px;
}

.validation-text {
    line-height: 1.3;
}
```

### Reglas

* Si `validation.enabled=False`, el QR no debe renderizarse.
* El QR debe aparecer automáticamente cuando aplique.
* No usar JavaScript.
* Variables deben permanecer en inglés.

---

## Endpoint público

Implementar endpoint:

```text
GET /public/validate_doc/<token>
```

### Reglas

Debe ser:

```text
público
sin autenticación
seguro
limitado
```

Debe respetar:

```text
external_document_validation_enabled
```

Si la validación está deshabilitada:

Mostrar:

```text
Validation unavailable.
```

Si token no existe:

Mostrar mensaje genérico.

Ejemplo:

```text
Document not found or validation unavailable.
```

No revelar detalles internos.

---

## Flujo de validación

Flujo:

```text
Recibir token
↓
Validar configuración global
↓
Buscar PublicDocumentValidation
↓
Verificar is_enabled
↓
Resolver documento
↓
Reconstruir payload
↓
Recalcular hash
↓
Comparar hash
↓
Mostrar resultado
```

Resultados:

```text
válido
inconsistente
anulado
revertido
cancelado
no disponible
```

---

## Información permitida públicamente

Puede mostrarse:

```text
Empresa emisora
Identificación fiscal
Tipo documental
Número documental
Fecha
Moneda
Total
Estado actual
Fecha de validación
```

No mostrar:

```text
IDs internos
asientos contables
cuentas contables
centros de costo
proyectos
costos internos
notas internas
datos bancarios
tracebacks
errores técnicos
```

---

## Documentación

Actualizar:

```text
docs/print-formats/
```

Agregar:

```text
validation-qr.md
designer-guide.md
jinja-context-reference.md
```

Documentar:

* Configuración global.
* URL pública.
* Fallback `https://cacaocontent.com`.
* Uso de `validation.enabled`.
* Uso de `validation.public_url`.
* Uso de `validation.qr_data_uri`.
* Funcionamiento del endpoint.
* Limitaciones de seguridad.
* Que no se guardan snapshots.

---

## Tests requeridos

### Configuración

Validar:

* Fallback `https://cacaocontent.com`.
* URL personalizada.
* Configuración habilitada.
* Configuración deshabilitada.

### Posting service

Validar:

* Se genera token al postear.
* No se genera token en borrador.
* No se duplica token.
* Se actualiza hash correctamente.

### Context builder

Validar:

* `validation.enabled`
* `validation.public_url`
* `validation.qr_data_uri`
* ocultamiento cuando está deshabilitado.

### Plantillas

Validar:

* Todos los formatos predeterminados tienen QR condicional.
* El QR aparece cuando aplica.
* El QR desaparece cuando no aplica.

### Endpoint público

Validar:

* Token válido.
* Token inexistente.
* Documento modificado.
* Documento anulado.
* Validación deshabilitada.
* No exposición de datos sensibles.

---

## Criterios de aceptación

La implementación estará lista cuando:

1. Exista configuración global de validación externa.
2. Exista URL pública configurable.
3. `https://cacaocontent.com` funcione como fallback.
4. El posting service genere tokens para documentos validables.
5. El token sea único y no predecible.
6. El hash sea determinístico.
7. El contexto de impresión incluya `validation`.
8. Todos los formatos predeterminados incluyan QR condicional.
9. El QR se oculte si la validación está deshabilitada.
10. El endpoint `/public/validate_doc/<token>` funcione sin autenticación.
11. El endpoint respete configuración global.
12. No se expongan datos sensibles.
13. Existan tests suficientes.
14. Exista documentación actualizada en `docs/print-formats/`.
