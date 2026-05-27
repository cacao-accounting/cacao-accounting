# Ejemplo: Factura de Venta

```jinja
<h1>{{ company.name }}</h1>
<h2>Invoice {{ invoice.number }}</h2>

<table>
  {% for item in invoice.items %}
  <tr>
    <td>{{ item.description }}</td>
    <td>{{ item.quantity | number }}</td>
    <td>{{ item.line_total | money(invoice.currency) }}</td>
  </tr>
  {% endfor %}
</table>

<strong>{{ invoice.grand_total | money(invoice.currency) }}</strong>
```
