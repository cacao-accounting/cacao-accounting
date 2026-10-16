# Guía de CSS para Formatos de Impresión

Cacao Accounting usa **WeasyPrint** para convertir HTML y CSS en documentos PDF. Para asegurar que tus templates se vean bien, sigue estas pautas.

## Regla @page

Usa la regla `@page` para definir el tamaño del papel y los márgenes.

```css
@page {
    size: letter portrait;
    margin: 1cm;
}
```

## Tablas

Para documentos con muchos ítems (como facturas), usa encabezados y pies de tabla estándar que se repitan a lo largo de las páginas.

```css
thead {
    display: table-header-group;
}
tfoot {
    display: table-footer-group;
}
```

## Clases Auxiliares

Se recomienda definir clases de utilidad para necesidades comunes:

```css
.text-right { text-align: right; }
.text-center { text-align: center; }
.bold { font-weight: bold; }
.mt-20 { margin-top: 20px; }
```

## Saltos de Página

Forzar un salto de página cuando sea necesario:

```css
.page-break {
    page-break-before: always;
}
```

## Limitaciones

- **Sin JavaScript**: Los scripts están estrictamente prohibidos y no se ejecutan.
- **CSS Moderno**: Aunque WeasyPrint soporta muchas características de CSS3 (Flexbox, Grid), evita propiedades muy complejas o experimentales.
- **Recursos Externos**: Las fuentes o imágenes externas deben alojarse en el mismo servidor o ser accesibles vía HTTPS.
