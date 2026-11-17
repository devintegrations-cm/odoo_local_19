{
    "name": "Clara Purchase Bridge",
    "version": "19.0.2.0.1",
    "category": "Purchases",
    "summary": "Cardholder table and access groups of the Clara corporate-card modules (read-only)",
    "description": """
Clara Purchase Bridge
=====================

Read-only base of the Clara corporate-card modules. Since 2.0.0 it books nothing: no method of this
module creates, confirms or writes a purchase order, and nothing is sent to Clara.

- Cardholder table (``clara.analytic.rule``, Purchases > Configuration > "Analítico por titular Clara"):
  the area and the analytic account (cost centre) of every cardholder, by Clara user uuid, email or
  name, with an area default. The connector's dashboard reads it to show the area and cost centre of
  each card and transaction. Editable by "Clara / Administrador" only.
- Access groups: "Clara / Lectura" reads the whole Clara menu without creating, editing or deleting
  anything (Accounting users get it); "Clara / Administrador" configures the API, runs the sync and
  edits the cardholder table (system administrators get it).
- The Clara fields of the purchase orders booked by earlier versions (transaction uuid, cardholder,
  merchant, charge, decision) stay on the order as a read-only trail, with the "Clara" tab and the
  "Desde Clara" filter. The national id column of earlier versions is dropped: the modules never
  store it again.
""",
    "author": "Libertario Coffee Roasters",
    "website": "https://www.libertariocoffee.com",
    "license": "LGPL-3",
    "depends": ["purchase", "account"],
    "data": [
        "security/clara_security.xml",
        "security/ir.model.access.csv",
        "data/clara_analytic_rule.xml",
        "views/clara_analytic_rule_views.xml",
        "views/purchase_order_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
