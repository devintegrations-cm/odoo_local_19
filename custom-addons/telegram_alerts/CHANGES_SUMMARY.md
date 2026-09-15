# Quick Changes Summary - Odoo 17 to 19

## Modified Files (3)

### 1. `__manifest__.py`
```python
# CHANGED:
'version': '19.0.1.0.0',  # was: '17.0.1.0.0'
```

### 2. `views/telegram_alerts_views.xml`
```xml
<!-- CHANGED: <tree> → <list> (Odoo 19 removed <tree> tag) -->
<list string="Telegram Alerts Configuration">
    ...
</list>

<!-- CHANGED: view_mode -->
<field name="view_mode">list,form</field>  <!-- was: tree,form -->
```

### 3. `data/server_actions.xml`
```xml
<!-- REMOVED from cron job: -->
<!-- <field name="numbercall">-1</field> -->
<!-- Field no longer exists in Odoo 19 ir.cron -->
```

## Unchanged Files (12)
All other Python, XML, CSV, and data files remain unchanged and are fully compatible with Odoo 19.

## Key Odoo 19 Changes Affecting This Module

1. **`<tree>` → `<list>`:** Odoo 19 replaced the `<tree>` view tag with `<list>`. All `<tree>` and `</tree>` must be `<list>` and `</list>`.
2. **`view_mode`:** Values using `tree` must use `list` (e.g., `tree,form` → `list,form`).
3. **`numbercall` removed from `ir.cron`:** The field that controlled how many times a cron runs was removed. Crons now repeat by default and stop only via `active=False`.
4. **`_sql_constraints` removed:** Not used in this module, so no impact.

## Testing Priority
1. Server actions appear in Action menu (list view)
2. Telegram messages send correctly
3. Product fields visible and functional
4. Cron job scheduled and runs properly
5. Validation constraints work (percentage 0-1)
