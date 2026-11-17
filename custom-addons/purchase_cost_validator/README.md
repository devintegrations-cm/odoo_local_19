# Validador de costos de compra (`purchase_cost_validator`) · Odoo 19

Keeps typing mistakes in purchase orders (price, quantity, unit of measure) out of the inventory cost.
Separate module: `purchase_price_validation` is not modified and keeps working as before.

## How a line is checked

The price typed is converted to the product's unit and the company currency, then compared with the rules
already in the system:

- **reference**: the product's cost (standard_price).
- **tolerance**: the product's "Variación de Costo" from `purchase_price_validation` (10 % by default).
- A product without cost shows "Sin referencia" (nothing to compare with).

| State | When | What the user sees |
| --- | --- | --- |
| Sin novedad | inside the tolerance | nothing |
| Revisar (yellow) | beyond the tolerance | yellow price, yellow banner |
| Desfase (red) | price 0, or more than 2× / less than ½ of the cost | red cell, red banner, a toast while typing |

Nothing blocks typing or confirming an order. A confirmed order with red lines is flagged
("Desfase de costo") and the lines are written in its chatter.

## At reception

When an incoming receipt still has red lines, or receives clearly more than what is pending on the order:

1. The receipt is flagged in red (list filter "Con desfase de costo").
2. The purchase reviewer gets a message (e-mail or Odoo inbox, as set in his preferences) with the table of
   lines, plus a to-do activity. Same problem twice = one message.
3. If "Retener la recepción" is on (default), only the reviewer or an inventory manager can receive it
   ("Recibir de todas formas", logged with his name). Anyone else sees the reason and a button to the order.
   Fixing the price on the order clears the flag and the receipt goes through normally.

Telegram: if `telegram_alerts` is installed with a connector whose identifier is `costos_compras`, the same
alert is sent there. WhatsApp is not available in Odoo Community.

## Settings

Compras › Configuración › Validador de costos: reviewer, go-live date, red threshold (times), hold receipts.
The general settings page only has a shortcut to it, because that page cannot be saved while point of sale
sessions are open.

## Tests

    odoo -d <db> -i purchase_cost_validator --test-enable --test-tags /purchase_cost_validator --stop-after-init

## Odoo 19 port (branch `devValidator_19`)

Same behaviour as the Odoo 17 module (`devValidator`); only what Odoo renamed changes:

- `purchase.order.line.product_uom` is `product_uom_id`; list views are `<list>`, not `<tree>`.
- `stock.picking.move_ids_without_package` is gone: the receipt uses `move_ids`.
- Products are `type = consu` (goods) plus `is_storable`; services and combos are not checked.
- `res.groups.users` is `user_ids`.
- The mark that identifies the automatic average-cost recalculation is `disable_auto_revaluation`
  (`disable_auto_svl` in 17). Both are ignored, so a receipt never raises a cost-edit alert.

Port checked on a clean Odoo 19 database: 17 tests pass, a real receipt of an average-cost product changes the
cost without alert, a manual incoherent edit alerts and saves the cost as typed.

## Who sees what

The configuration (menu, screen, settings shortcut and its table) is for administrators only (`base.group_system`). Everybody who creates orders or receipts sees the red and yellow warnings where they apply; the validator has no app, no menu and no screen of its own for them.

## Independent of purchase_price_validation

The validator has its own `porcent_variation` field (same name, label and default as that module, so both can coexist) and does not depend on it. That module blocks orders and receipts when its two settings are on, and Odoo's settings page turns them on by deleting their parameters; confirming through its dialog also skips this validator. The per-product margin is edited in the product's "Validador de costos" tab (administrators only).
