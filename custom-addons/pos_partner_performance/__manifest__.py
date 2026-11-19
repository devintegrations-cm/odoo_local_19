{
    "name": "POS Partner Performance",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "summary": "Frequent customers ranked per point of sale, over the last N days",
    "description": """
POS Partner Performance
=======================

Optional module that reduces what the Point of Sale computes for customers.

* Frequent customers ranked per point of sale and over the last N days,
  instead of counting every POS order of the company on each load.
  Enabled per point of sale.

The companion module ``pos_partner_performance_settle_due`` (installed
automatically together with ``pos_settle_due``) stops computing the amount due
of every customer.
""",
    "author": "Miguel Bolivar, Libertario Coffee",
    "website": "https://www.libertariocoffee.com",
    "license": "LGPL-3",
    "depends": [
        "point_of_sale",
        "pw_pos_default_customer",
    ],
    "data": [
        "views/pos_config_views.xml",
    ],
    "images": [
        "static/description/01_configuracion.png",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
