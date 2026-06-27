# Ejemplo: Comprobante de Pago

```jinja
<h1>{{ company.name }}</h1>
<h2>{{ payment.number }}</h2>
<p>{{ payment.party_name }}</p>
<p>{{ payment.paid_amount | money(payment.currency) }}</p>

{% for reference in payment.references %}
  <div>{{ reference.reference_number }} - {{ reference.allocated_amount | money(payment.currency) }}</div>
{% endfor %}
```
