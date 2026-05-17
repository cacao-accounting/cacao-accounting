# Rule Priority & Resolution

The system uses a hierarchical resolution strategy to determine which tax rules apply to a transaction.

## Priority Levels

Rules are resolved in the following order of specificity (highest priority first):

1. **Item**: Specific rules assigned to a product or service profile.
2. **Party**: Rules specific to a Customer or Supplier (e.g., Exempt Customer, Large Taxpayer).
3. **Transaction**: Rules applied to a specific transaction type or template.
4. **Company**: Default fallback rules for the entity.

## Merge Strategies

When multiple rules conflict or overlap, the `merge_strategy` defines the outcome:

| Strategy | Description |
| :--- | :--- |
| `override` | A higher priority rule replaces lower priority rules for the same concept (e.g., IVA). |
| `append` | Higher priority rules are added alongside lower priority ones. |
| `exclude` | A higher priority rule removes rules for that concept from lower levels (e.g., an exempt customer excludes VAT). |
| `replace_group` | A higher priority rule replaces ALL rules from lower levels. |
