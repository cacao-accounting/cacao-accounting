# Ejemplo: Comprobante Contable

```jinja
<h1>{{ company.name }}</h1>
<h2>{{ journal_entry.number }}</h2>

<table>
  {% for line in journal_entry.items %}
  <tr>
    <td>{{ line.account_code }}</td>
    <td>{{ line.description }}</td>
    <td>{{ line.debit | money(journal_entry.currency) }}</td>
    <td>{{ line.credit | money(journal_entry.currency) }}</td>
  </tr>
  {% endfor %}
</table>
```
