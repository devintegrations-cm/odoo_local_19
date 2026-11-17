# -*- coding: utf-8 -*-
{
    "name": "Clara – Tarjetas corporativas (solo lectura)",
    "version": "19.0.2.0.2",
    "category": "Accounting/Localizations",
    "summary": "Dashboard de solo lectura de las tarjetas y transacciones Clara: sincronización semanal y trazabilidad contra las órdenes de compra",
    "description": """
Clara Connector
===============

Libertario fork of Clara's official connector (github.com/davidzn-clara/odoo-clara-connector), reduced
since 2.0.0 to a read-only mirror of Clara:

- Only GET calls to Clara's API (plus the OAuth token). Nothing is written to Clara: no comments, labels,
  approvals, rejections or card locks.
- No purchase order is created, confirmed or modified. The link between a transaction and its order is
  computed from the order code (P#####) the legalization bot writes on the first line of the Clara
  comment, and the reconciliation state follows the reviewer's decision in Clara (validationStatus).
- One weekly scheduled action, Sunday 22:00 America/Bogota, that asks Clara only for the transactions
  created or updated since the last sync (lastUpdateDate filter, pages of 100) and the cards, and writes
  only the records that changed. "Sincronizar ahora" runs the same for administrators.
- Clara > Dashboard: cards (list grouped by area, blocked in red; kanban with the count per status),
  transactions (cardholder, date, merchant, amount, Clara status, linked order, reconciliation state;
  filters by month, cardholder, area and state) and traceability (pivot cardholder x month with the count
  and amount per reconciliation state; graph of the reconciled percentage per month).
- Cards keep the cardholder, the last four digits, the type, the status, the monthly limit, the area and
  the analytic account of the cardholder table; the full card number and the national id are never stored.
- Groups "Clara / Lectura" (reads everything, writes nothing; Accounting users get it) and
  "Clara / Administrador" (API settings and "Sincronizar ahora"), defined in clara_purchase_bridge.
""",
    "author": "Clara, Libertario Coffee Roasters",
    "website": "https://www.clara.com",
    "license": "LGPL-3",
    "depends": [
        "base",
        "account",
        "purchase",
        "clara_purchase_bridge",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/clara_transaction_views.xml",
        "views/clara_card_views.xml",
        "views/clara_sync_log_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
