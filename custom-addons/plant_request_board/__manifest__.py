{
    "name": "Plant Request Board",
    "version": "19.0.1.10.2",
    "category": "Inventory",
    "summary": "Board for the plant with every order by channel, new-order alerts and an AI briefing per order",
    "description": """
Plant Request Board
===================

Stores ask the plant for product by creating an internal transfer from a plant
warehouse to their own (PLANT/INT/xxxxx); customers get deliveries from the plant.
This module gives the plant a live view of those requests instead of reading them
store by store. Plants, stores and channels are records: a new plant, store, product
or channel needs no deployment.

- Kanban board grouped by store (or by stage) with days waiting, lines, coffee in
  grams and packaging units per request; stages with colours (Nueva, En alistamiento,
  Lista para despachar, Entregada, Cancelada) driven by the preparation ticks, a
  tick per line × presentation with who and when, progress per request, a
  "Validar entrega" button, live reload of the views through the bus, a
  one-page delivery note (PDF, letter) printable from the card, the form and the list,
  green coffee alerts per coffee line (shrinkage, cumulative by request date) and the
  supplies of the stores and of the bills of materials against the stock.
- A "Planta" tab on the transfer with requested vs delivered per line, stock
  available at the plant, and comparison with the store's usual quantities.
- New-order alert inside Odoo: Discuss channel message and a browser chime for
  the plant users while they are in the Planta app. Orders created by plant
  staff do not ring.
- Consolidation: the plant's sheet with one automatic row per coffee line × grams ×
  grind, generated from the plant fields of the products (classified from their
  names, reviewed in a wizard, duplicated references added up in their master), and
  a production plan (ordered − stock at the plant = to produce, kg to roast per
  coffee line), replacing the plant's manual spreadsheet.
- Optional briefing written with the Anthropic API from facts computed in Odoo
  (nothing is invented: quantities, stock and history come from the database).
""",
    "author": "Libertario Coffee Roasters",
    "website": "https://www.libertariocoffee.com",
    "license": "LGPL-3",
    "depends": ["stock", "mail", "product", "sale_stock"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "data/ir_config_parameter.xml",
        "data/ir_cron.xml",
        "data/discuss_channel.xml",
        "security/ir.model.access.csv",
        "data/plant_kind.xml",
        "data/plant_channel.xml",
        "data/plant_sheet_template.xml",
        "views/stock_warehouse_views.xml",
        "views/stock_picking_views.xml",
        "views/plant_channel_views.xml",
        "views/product_template_views.xml",
        "views/plant_coffee_line_views.xml",
        "views/plant_wizard_views.xml",
        "views/consolidation_views.xml",
        "views/plant_sheet_template_views.xml",
        "views/plant_kind_views.xml",
        "views/res_config_settings_views.xml",
        "report/plant_delivery_note_report.xml",
    ],
    "assets": {"web.assets_backend": ["plant_request_board/static/src/scss/plant_board.scss", "plant_request_board/static/src/js/plant_alert_service.js", "plant_request_board/static/src/js/plant_kanban_view.js", "plant_request_board/static/src/sheet/plant_sheet.js", "plant_request_board/static/src/sheet/plant_sheet.xml", "plant_request_board/static/src/sheet/plant_sheet.scss"]},
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
    "auto_install": False,
}
