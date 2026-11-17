# Plant Request Board · Odoo 19

## Odoo 19 port (branch `devPlant_19`)

Same behaviour as the Odoo 17 module (`devPlant`, 17.0.1.3.0); only what Odoo renamed or removed changes:

- Units of measure have no categories in Odoo 19: `plant.sheet.row._is_weight` takes the units whose chain of
  reference units ends in the gram (kg → g). Odoo 17 still compares the gram's category. The grams of a line are
  read from the unit's name in both versions (`stock.picking._plant_grams`).
- `models.Constraint` class attributes instead of `_sql_constraints` (the latter is ignored in 19).
- `stock.move` has no `name` and products no `uom_po_id`; products are `type = consu` + `is_storable` (tests and
  the product domain of the workbook rows).
- The kanban opens every column through `DEFAULT_OPEN_GROUP_LIMIT` (19) as well as `MAX_NUMBER_OPENED_GROUPS` (17).
- Views: `<list>` instead of `<tree>`, kanban template `card`, search group without `expand`,
  no `default_period` on the "Esta semana" date filters (19 validates it and only takes year, month or quarter
  values; the week is picked in the filter's own dropdown), `ir.cron` without `numbercall`.
- Migrations renamed `19.0.1.1.0`, `19.0.1.2.0`, `19.0.1.3.0`, `19.0.1.4.0`, `19.0.1.5.0`, `19.0.1.6.0`, `19.0.1.7.0`, `19.0.1.10.0`, `19.0.1.10.1`, so a database that installed 19.0.1.0.0 runs them (1.8.x and 1.9.0 have no migration).
- `read_group` and `@route(type="json")` are deprecated in 19 (warnings only); kept as in 17.

Checked on a clean Odoo 19 database (tests) and with `-u` on a copy of the production-size 19 database.


Stores ask the plant for product by creating an internal transfer whose source is a
plant warehouse (`PLANT/INT/xxxxx`, PLANT/Existencias → `<store>/Existencias`); customers
get deliveries from the plant. This module turns those transfers into a live board for
the plant. Nothing about it is static: plants, stores, channels and their rules are
records of the database, so a new plant, store or channel needs no deployment.

## What it adds

- **Inventario › Planta › Solicitudes de tiendas**: kanban grouped by store (or by
  stage, day) with days waiting, lines, coffee in kg and packaging units. List view
  with totals.
- **"Planta" tab** on the transfer: requested vs delivered per line, stock available
  at the plant, the store's usual quantity in the last 90 days, and flags
  (`faltante`, `nuevo para esta tienda`, `más del doble de lo usual`).
- **New-order alert inside Odoo**: a message in the Discuss channel "Planta · solicitudes de tiendas"
  (inbox, chat sound, mobile push) and, for the configured plant users, a browser notification with a
  chime that plays only while they are inside the Planta app. Orders created by plant staff do not ring.
- **Briefing**: a cron every 5 minutes writes the analysis of pending requests. With an
  Anthropic API key configured, a 3–5 sentence summary is written from the facts Odoo
  computed (the model never sees the database, only the JSON of facts). Without a key
  the facts table alone is written.

## Products and rows (records, not code)

- **Plant fields on the product** (`product.template`, tab *Planta*): `plant_kind_id` (how the plant counts it:
  bulk coffee, packed coffee, ready to sell, supply, green coffee — green coffee never counts as bulk nor in the
  sheet), `plant_coffee_line_id` (`plant.coffee.line`: name, order and
  colour of the line), `plant_net_grams`, `plant_grind` (beans / ground), `plant_in_sheet` (counts in the sheet
  and the plan) and `plant_master_id` (the equivalent reference this one adds up in; a variant takes the master's
  values). Every calculation reads these fields, never the product name.
- **Classifier**: when a product is created, its fields are proposed from its name with the vocabulary of
  Planta › Tipos de línea and Ajustes (grind words, ignored words such as the barcode mention) and the known
  coffee lines; a line named for the first time is created (a bulk product "… - X" names it through its suffix). A product edited by hand or
  applied in the wizard is *reviewed* (`plant_manual`) and never touched again; the automatic ones are classified
  again when the vocabulary changes or their name changes. **Planta › Clasificar productos** shows the proposal
  next to the current values and writes it only on *Aplicar*.
- **Duplicated references**: **Planta › Referencias duplicadas** groups the products with the same line, grams
  and grind (or the same name without the ignored words), proposes the busiest one as master and writes
  `plant_master_id` on the others when confirmed. Nothing is deleted or archived.
- **Rows of the sheet**: generated from the products, one per coffee line × grams × grind ("Paz 340 en grano";
  the grind split is a setting), bulk coffee and the bags of the preparation size in "<Line> Preparación 2.5"
  (the size is a setting), one row per ready product. They are `plant.sheet.row` records with `is_auto`, synced
  every time the sheet opens, so the plant can still type INVENTARIO on them or archive one to hide it. Manual
  rows stay for the **kits** (kit row + component rows × factor) and for **exceptions** (a manual row with
  products and the *Excepción* flag takes them away from their automatic row). The legacy plain rows of 1.4.0
  are kept but inert (`exception = False`).
- The **CAFE** tab is gone (model, client, Excel); its seeded rows are removed by the 1.5.0 migration.
- The 1.5.0 migration takes the coffee lines and the product fields from the legacy rows (those products count as
  reviewed), classifies every other product from its name as the board did live before, and reads the open order
  lines again. Review the result in Planta › Productos de planta and Planta › Clasificar productos.

## Stages, ticks and delivery

- **Stages** (`plant_stage`): Nueva, En alistamiento, Lista para despachar, Entregada, Cancelada, with the same
  colours in the kanban, the list and the sheet. The open stages follow the preparation ticks (none / some /
  all); Entregada and Cancelada follow the transfer. The stage can be set by hand in the statusbar of the
  *Planta* tab and holds until the ticks change. The active sheet and the roasting plan count Nueva and En
  alistamiento only; the sheet offers "Listas para despachar", "Despachadas" and "Todos los pedidos" scopes.
- **Ticks** (`plant.request.check`): one per line × presentation of the request (the same key as the automatic
  rows of the sheet: "Paz 200 en grano", "Paz Preparación 2.5", a ready product; supplies by product), kept in
  step with the order lines. A visual guide only: quantities, moves and stock are never touched. Who ticked and
  when are kept; the request shows its progress (%). In the sheet every cell shows the ticks of its lines and
  toggles them.
- **Validar entrega**: button on the card, the list and the form. It runs the standard validation of the
  transfer with the user's own rights, posts a note in the chatter and the stage becomes Entregada. It
  validates at once only when every tick is done or every open line has its quantity, and nothing is short of
  stock; otherwise a confirmation lists the lines that would be delivered in full and the lines whose demand
  exceeds the stock at the plant (e.g. 7.5 kg asked, 5 kg in stock), and the plant decides. Any wizard Odoo
  itself asks for (backorder) is shown too.
- The 1.7.0 migration keeps the stage every open request had: its ticks are created and, for Lista para
  despachar, created done; En alistamiento and Nueva hold until a tick changes.
- **Live**: new requests ring and notify the plant users (bus + Discuss channel); ticks, stage changes and
  deliveries send a silent bus update, and the kanban, the list and the sheet reload in place.

## Delivery note (PDF)

- **Remisión de solicitud** (`plant_request_board.action_report_plant_delivery_note`): one US Letter page per
  request, printable from the card, the form, the list (several at once through *Imprimir*) and the standard
  *Print* menu. Header with the company logo and colours (`res.company.logo`, `primary_color`,
  `secondary_color`, as set in the document layout), transfer number, date, external reference
  (`sale.client_order_ref` or `origin`), sale, channel, store or customer and stage. The table lists every line
  (coffee and supplies, grouped by kind): reference, name, coffee line, grams, grind, quantity, unit and kg, with
  totals. Below, the full delivery address (store warehouse contact or the delivery contact: name, street,
  apartment, city / state / zip, country, phone), the observations (transfer note and the store's last comment)
  and the signature boxes for who dispatches and who receives. Totals are separate: kg of coffee (bulk and
  bags) and bags, ready units (capsules, drips, drinks) and supply units; supplies never show kg. The note is
  always one page: up to 24 rows at 10px, 44 at 8px, 100 in two columns, more in three. A cancelled request
  prints with a red band and a "CANCELADA" watermark so nobody dispatches it.

## Green coffee and supplies

- **Shrinkage per coffee line** (`plant.coffee.line.shrinkage`, %; empty uses *Merma de tostión por defecto* of
  Ajustes › Planta): `kg verde = kg a tostar ÷ (1 − merma)`.
- **Green coffee of a line**: the products of kind *Café verde* with that line and, when manufacturing is
  installed, the green components of the bills of materials of the line's roasted coffee (bulk, or the bulk
  inside a bag). Stock at the plants in kg; a negative stock reads as zero with a warning.
- **Cumulative alerts**: the pending requests (Nueva, En alistamiento) are walked in order of arrival; each one
  takes the roasted coffee of its lines that is in stock, what is left has to be roasted, and its green coffee
  comes out of the line's green stock. Per request and line: green (enough), yellow ("Te quedan solo X kg"
  below the line's minimum, `green_minimum_kg` or the default of the settings), red ("Para esta solicitud te
  faltan X kg de café verde"). Shown on the card and the form (`plant_green_alert_html`,
  `plant_green_status`) and in the sheet's *Café verde* block (per line and per request).
- **Supplies of the bills of materials** (`plant.sheet._plant_bom_supplies`): with manufacturing installed,
  the components that are not coffee (bags, valves, labels…) of what the plan has to make, against the stock at
  the plant, with the same alert (minimum: *Mínimo de insumos por fabricar*). Block *Insumos por fabricar* of
  the sheet and of the Excel.
- **Supplies the stores ask for** (cups, lids, kraft bags, pastry paper, postcards…): classified by the plant
  kind *Insumo* of the product, never by name. On the card, on the note and in the sheet's *Insumos pedidos*
  block (per store column, total, stock at the plant, to buy), in their own unit; they never add a gram to the
  roasting.
- The preparation rows show bulk kg and bags apart under the inventory; every negative stock (rows, supplies,
  green coffee) reads as zero with "Inventario negativo en Odoo: falta registrar producción/empaque".

## Stock at the plant and the roasting plan

- A negative stock in Odoo (production or packing not registered yet) **never adds** to what has to be made:
  `kg a tostar = max(0, kg pedidos − max(0, inventario))`, in the sheet and in the plan. The negative figure is
  shown as a warning (orange cell and tooltip in the sheet, "Inventario negativo en Odoo: falta registrar
  producción/empaque" on the plan row, a comment in the Excel).
- The sheet and the plan show their totals side by side (note under the sheet, "Comparar con la hoja" button on the plan). They differ
  by design: the plan joins every channel and discounts the plant's stock on all of them, per master reference;
  the sheet discounts stock only in PEDIDOS TIENDAS (OTROS and ATTENZA are roasted in full, as in the workbook),
  pools in one row the stock of every reference of the row and explodes the kits.
- The AI briefing needs an Anthropic key: without one the requests are not queued, the cron does nothing and
  Ajustes says "Análisis IA desactivado"; the button on the transfer still writes the facts table.

## Plants, stores and channels (records, not code)

- **Plants**: warehouses flagged *Almacén de planta* (`stock.warehouse.plant_is_plant`), picked in
  Inventario › Ajustes › Planta or on the warehouse. Every internal transfer or delivery that leaves a plant is
  a request; `plant_warehouse_id` on the transfer and its lines says which plant, and the board, the
  consolidation, the production plan and the sheet filter by it. Flagging (or unflagging) a warehouse
  classifies its transfers again, in batches.
- **Stores**: warehouses flagged *Es tienda* (`plant_is_store`). The first request a warehouse receives
  without matching any channel rule flags it, so a new store (Rivana, WeWork…) gets its column in
  PEDIDOS TIENDAS at once. *Columnas de la hoja* (`plant.sheet.column`) is only an optional layer over those
  columns: alias, order, header colour, hidden (hidden columns still count in TOTAL BOLSAS). EVENTO groups the
  event warehouses there.
- **Channels** (`plant.channel`, Planta › Canales): Tiendas, Eventos, E-commerce, Attenza, Alianzas, Otros,
  in order of evaluation. A request takes the first channel with a rule that matches it; every rule is a
  relation: destination warehouses, pricelists, sales teams, partner tags, partners (the partner, its parents
  and its `commercial_partner_id`; an optional rule, empty by default: Attenza is recognised by its pricelists)
  and the Shopify flag of the sale. Without a match, the channel marked as fallback for transfers
  (Tiendas) or for deliveries (Otros) applies. Each channel says which tab of the sheet it feeds. A rule
  change classifies the open requests again at once. Transfers keep `plant_channel_id` and the channel's
  code in `plant_channel` (filters and pivots saved before 1.4.0 keep working).
- A request is read from the locations, never from the operation type: whatever leaves a location of a plant
  towards another warehouse (a store's own internal transfer or receipt included, e.g. LAUME/INT/… with source
  PLANT/Existencias) or towards a customer. A transfer between two stores is not a request.
- The 1.4.0 migration flags the warehouse the old `plant_warehouse_code` setting named, links the records the
  old text rules named (warehouse codes, pricelist and team names, tags) to the channels, and flags as stores
  the destinations of the store requests and the warehouses of the PEDIDOS TIENDAS columns. Check the result in
  Planta › Canales after deploying.

## Security

- **Groups**: the module adds no group of its own; it uses the standard Inventory groups as Odoo does.
  *Inventario / Usuario* (`stock.group_stock_user`) works the board, the sheet, the plan, the ticks, the note
  and the delivery; *Inventario / Administrador* (`stock.group_stock_manager`) owns the configuration: channels,
  kinds, coffee lines (shrinkage, minimum), plant products, classifier and duplicate wizards, rows and columns of
  the sheet, the typed INVENTARIO (`plant.sheet.set_inventory`), the settings menu and the rows of the plan
  (`plant.production.plan`: users read; the rows are created and dropped with sudo on behalf of the user who
  opens the plan). The settings form itself also needs the Settings right, as everywhere in Odoo. The 1.10.1
  migration removes the two Planta groups that 1.10.0 had introduced without taking any right away (a
  «Planta / Jefe» who is not an inventory administrator is listed in the log, never promoted automatically).
- **Anthropic key**: never in the database. `stock.picking._plant_anthropic_key` reads the environment variable
  `PLANT_ANTHROPIC_API_KEY`, else the option `plant_anthropic_api_key` of odoo.conf. The 1.10.0 migration
  removes the old `ir.config_parameter` value; Ajustes shows whether the briefing is active and where the key
  goes.
- **sudo() audit** (every call reads configuration or does housekeeping a store user could not do by rights,
  never widens what the user sees): plant warehouses, channels, kinds (classification of a transfer created by
  a store user); bills of materials (classifier, green coffee, duplicates); the tick sync and the store flag
  (written when a store creates a request); the plan rows (owned by the manager); the automatic rows of the
  sheet (synced when a user opens it); bus targets and Discuss channel (notifications); the last comment of
  the transfers (one query for the batch); `ir.config_parameter` reads and the plant staff list.

## Performance

- Stock is read with one `stock.quant` read_group per sheet load, plan or allocation (`plant.sheet._stock_by_product`),
  never `qty_available` per product and row; the classifier never searches the products (the lines are records,
  a bulk product "… - X" names a new line through its suffix); the last comment of a batch of transfers is one
  query; one sheet load computes the plan rows once and shares them with the plan total and the BoM supplies.
- Measured on a copy of the database with 1,000 generated requests (1,052 pending, 5,085 open lines), Odoo 17,
  best of 3, before 1.10.0 → after:

  | Operation | Before | After |
  |---|---|---|
  | Sheet, PEDIDOS TIENDAS (open) | 2.37 s · 10,680 queries | 0.43 s · 230 queries |
  | Sheet, OTROS PEDIDOS (open) | 0.27 s · 505 queries | 0.24 s · 213 queries |
  | Roasting plan | 0.15 s · 146 queries | 0.15 s · 144 queries |
  | Green coffee allocation | 0.17 s · 427 queries | 0.16 s · 194 queries |
  | Kanban page, 80 cards (card, ticks, green alert) | 0.18 s · 376 queries | 0.17 s · 139 queries |
  | Kanban, 500 cards | 0.30 s · 369 queries | 0.29 s · 132 queries |
  | Delivery note data, 50 requests | 0.11 s · 282 queries | 0.05 s · 233 queries |
  | Reclassify every open line (a setting changed) | 0.49 s · 724 queries | 0.32 s · 581 queries |

  The sheet was rebuilding the classifier rules for every supply line (`_plant_short_name`) and asking the
  database for the gram unit (`env.ref`) for every line; both are now resolved once (the gram unit with an
  `ormcache`).
- Odoo 19: no deprecated `read_group` (the history of the briefing uses `_read_group`), no `type="json"` routes
  (the Excel export is an http route).

## Settings

Nothing the plant reads, or that is matched against names in the database, is written in the code:

- **Inventario › Ajustes › Planta**: plant warehouses, plant users, Discuss channel, the classifier's words
  (beans / ground words, ignored words), the abbreviations of the card, rows per group on the card, the
  preparation bag size and the grind split of the automatic rows, the shrinkage and minimums, the history
  window of the briefing (default 90 days) and the Anthropic model (the key lives on the server). Each scalar field is an `ir.config_parameter` (`config_parameter=` on `res.config.settings`), read by
  the models through `_plant_get`; the plant warehouses are the flag on `stock.warehouse`.
- **Planta › Tipos de línea** (`plant.kind`): label, icon, order and the keywords the classifier uses to propose
  the kind of a new product (bulk coffee, packed coffee, ready to sell, supplies). The code of a kind is fixed
  because it decides how the line is counted; a keyword change classifies the automatic products again.

## Tests

    odoo -d <db> -i plant_request_board --test-enable --test-tags /plant_request_board --stop-after-init

## Documents

- `CHANGELOG.md`: versions 1.4.0 to 1.10.0 and the deployment steps for each Odoo line.
- `doc/guia_planta.md`: short guide in Spanish for the plant team (board, ticks and stages, sheet, plan, note, delivery).
- The 1.10.0 commit message and the README section *Performance* hold the benchmark; the induction checklist
  (Bogotá, 8–14 November 2026) is kept with the project documents.
