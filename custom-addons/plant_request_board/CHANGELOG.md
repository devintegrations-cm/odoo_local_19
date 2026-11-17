# Changelog · plant_request_board

Same functionality on Odoo 17 (`17.0.x.y.z`, branch `feature/plant-dynamic-17`) and Odoo 19 (`19.0.x.y.z`,
branch `feature/plant-dynamic-19`). Every version below exists in both; only version-compatibility code differs
(list/tree views, kanban `card`, `models.Constraint` attributes, product `is_storable`, `group_ids`, migration
folder names). 47 automated tests, identical on both.

## 1.10.2 — 2026-11-10 · Sheet readability
- The sheet (Consolidado) states its own text colour and font: on Odoo 19 the text of the action inherited a light
  grey and Calibri could resolve to a thin face, so the quantities, the request codes and the supplies were almost
  invisible. Dark text everywhere, Arial, a darker empty tick box and a larger inventory detail. Nothing else
  changes.

## 1.10.1 — 2026-10-30 · Standard Inventory groups
- The two Planta groups of 1.10.0 are gone: the module uses `stock.group_stock_user` (board, sheet, plan, ticks,
  note, delivery) and `stock.group_stock_manager` (channels, kinds, lines, plant products, wizards, rows and
  columns, typed inventory, settings menu, the plan's rows), in access rights, menus, server actions and the
  Python checks. Migration: the groups are removed without taking rights away; a «Planta / Jefe» who is not an
  inventory administrator is listed in the log for the administrator to decide. Deliveries short of stock stay
  as they were (Odoo allows negative stock after the explicit confirmation).

## 1.10.0 — 2026-10-30 · Performance, security, key on the server
- Sheet: the classifier rules and the gram unit are resolved once per load (PEDIDOS TIENDAS with 1,052 pending
  requests: 2.37 s / 10,680 queries → 0.43 s / 230 queries); the plan rows are computed once per load; the
  classifier no longer searches the products (the bulk-coffee prefix setting is gone); the last comment of a
  batch of transfers is one query.
- Groups Planta / Usuario and Planta / Jefe (replaced by the standard Inventory groups in 1.10.1).
- The Anthropic key is read from `PLANT_ANTHROPIC_API_KEY` (environment) or `plant_anthropic_api_key`
  (odoo.conf), never from `ir.config_parameter`; the migration removes the stored value.
- A plant user without e-mail can still validate (the note is signed by OdooBot). Briefing history on
  `_read_group`.

## 1.9.0 — 2026-10-30 · Green coffee and supplies
- Shrinkage per coffee line (default in the settings): kg verde = kg a tostar ÷ (1 − merma). Green coffee of a
  line: products of kind *Café verde* with the line and, with manufacturing, the green components of the
  roasting BoM. Cumulative alerts per request in order of arrival (roasted stock first): green / yellow (below
  the line's minimum) / red (missing), on the card, the form and the sheet's *Café verde* block.
- Supplies of the bills of materials of what has to be made against the stock (*Insumos por fabricar*);
  supplies the stores ask for in their own unit in the *Insumos pedidos* block, never kg; bulk kg and bags
  shown apart in the preparation rows; every negative stock reads as zero with a warning.

## 1.8.1 — 2026-10-30 · Adjustments before Phase 5
- Migrations keep the stage every open request had (snapshot in 1.4.0 and 1.7.0 pre-migrations, restored by
  1.7.0 with the first ticks).
- *Validar entrega* validates at once only when every tick is done or every line has its quantity and nothing
  is short; otherwise a confirmation lists the lines delivered in full and the shortages.
- The note is always one page (24 rows at 10 px, 44 at 8 px, 100 in two columns, more in three), prints a
  CANCELADA band and watermark on cancelled requests, separates kg of coffee from units of supplies and takes
  logo and colours from the company's document layout.

## 1.8.0 — 2026-10-30 · Delivery note
- *Remisión de solicitud*: one US Letter page per request, printable from the card, the form and the list
  (several at once). Header with logo and colours, references, sale, channel, store/customer, stage; every
  line with reference, name, line, grams, grind, quantity, unit and kg; delivery address; observations;
  signature boxes.

## 1.7.0 — 2026-10-29 · Stages, ticks, delivery, live reload
- Stages Nueva / En alistamiento / Lista para despachar / Entregada / Cancelada driven by the preparation ticks
  (manual hold until the ticks change), same colours everywhere; the active sheet and the plan count Nueva and
  En alistamiento; scopes Listas / Despachadas / Todos.
- Ticks per line × presentation (`plant.request.check`), kept in step with the lines, with who and when;
  progress per request; ticks per cell in the sheet.
- *Validar entrega* on the card, the list and the form; bus update and in-place reload of kanban, list and
  sheet.

## 1.6.0 — 2026-10-29 · Corrections with production data
- Negative stock never adds to what has to be made (plan and sheet), shown as a warning; plan ↔ sheet
  comparison ("Comparar con la hoja").
- Requests are read from the locations, not the operation type (a store's own transfer or receipt from the
  plant is a request; store → store is not). Attenza by pricelists. Fifth kind *Café verde*; ROLLO, EMPAQUE,
  INFUSION, PAPEL are supply words. Duplicate finder flags groups whose internal references or BoMs differ.
  AI briefing silent without a key.

## 1.5.0 — 2026-10-29 · Products and automatic rows
- Plant fields on the product (kind, coffee line, net grams, grind, counts in the sheet, master reference) filled
  by a classifier on create and reviewed in *Clasificar productos*; *Referencias duplicadas* wizard.
- Automatic rows of the sheet per line × grams × grind from the products; manual rows only for kits and
  exceptions (legacy rows kept inert). The CAFE tab removed. Plan grouped by master reference.

## 1.4.0 — 2026-10-29 · Dynamic plants, stores and channels
- Plants and stores are flags on the warehouse; a store gets its column with its first request; *Columnas de
  la hoja* becomes an optional layer (alias, order, colour, hidden).
- Channels are `plant.channel` records with rules as relations (warehouses, pricelists, teams, tags, partners,
  Shopify flag), an evaluation order, the sheet tab each one feeds and a fallback per kind of transfer; the
  old text settings are migrated to records.

## Deployment

Production is Odoo 17. Steps for a database at 17.0.1.2.0 (or 19.0.1.0.0 on the Odoo 19 line):

1. Back up the database (the migrations rewrite the plant columns of `stock_picking` and `stock_move` by SQL and
   reclassify the open requests).
2. On the server, set the Anthropic key if the AI briefing is wanted: `PLANT_ANTHROPIC_API_KEY` in the
   environment of the Odoo service, or `plant_anthropic_api_key = …` under `[options]` in odoo.conf. Without it
   the briefing stays off (Ajustes says so).
3. Deploy the branch (`feature/plant-dynamic-17` or `feature/plant-dynamic-19`) and update the module:
   `odoo -d <db> -u plant_request_board --stop-after-init`. The migrations run in order (1.3.0 … 1.10.0) and log
   one line each: channels linked from the old text settings, coffee lines and products classified, stages kept
   and ticks created, groups assigned, key removed. No full recomputation of the transfer tables is triggered
   (every new stored column is created by SQL first).
4. Check the log for `plant_request_board 1.x.0:` lines and for `Prepare computation` (there must be none for
   stock.picking / stock.move).
5. After the update: Planta › Canales (pricelists of Attenza and E-commerce, warehouses of Eventos/Comercial),
   Planta › Productos de planta (filter *Sin clasificar* and *Clasificación automática*; set the line of the
   green coffee products), Planta › Líneas de café (shrinkage, minimum), Ajustes › Usuarios (the plant team as
   Inventario / Usuario, the person in charge as Inventario / Administrador with the Settings right), and the
   checklist in the Spanish guide (`doc/guia_planta.md`).
6. Odoo 19 line: the same steps; the migration folders are `19.0.x.y.z`.
