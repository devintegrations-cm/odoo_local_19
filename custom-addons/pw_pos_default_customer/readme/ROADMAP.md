- **The default customer must be among the contacts the POS loads.** A POS session only loads
  about 100 partners (the most used ones), so a customer outside that list cannot be resolved
  in the session. This module forces the configured customer into that list; without it the
  order would simply start with no customer and no visible symptom at all.
- **Refund orders inherit the default customer too.** A refund created from the Orders screen
  starts with the configured customer, so the refund may end up attributed to the generic
  customer instead of the original buyer. Check the customer before validating a refund. This
  is the inherited behaviour of the feature, not something the migration changed.
- Saving the Settings page may log a server warning about `pos_customer_id` not being properly
  saved. The value *is* saved (through the related field); the warning comes from the generic
  `pos_*` prefix handling in Odoo's POS settings and is harmless.
- `static/description/icon.png` is 512x512 px, while the core modules use 100x100 px. It
  should be resized or replaced.
- The help text shown under the **Default Customer** setting is written in Spanish
  ("Cliente asignado automaticamente a cada pedido nuevo", in `views/pos_config_view.xml`)
  inside an otherwise English module. It should be written in English and translated through
  the `i18n` files.
