{
    "name": "POS Partner Performance - Settle Due",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "summary": "Do not compute the amount due of every customer in the Point of Sale",
    "description": """
POS Partner Performance - Settle Due
====================================

Bridge between ``pos_partner_performance`` and ``pos_settle_due`` (Enterprise).

``pos_settle_due`` computes the amount due (orders and invoices) of every
customer the POS loads: when the POS opens, after every customer search, and
again after every sale paid with the customer account.  On large customer
accounts each computation takes tens of seconds.

This module stops those computations, per point of sale (enabled by default).
The amount due is still available in the backend (Accounting).

Installed automatically when ``pos_partner_performance`` and
``pos_settle_due`` are both installed.
""",
    "author": "Miguel Bolivar, Libertario Coffee",
    "website": "https://www.libertariocoffee.com",
    "license": "LGPL-3",
    "depends": [
        "pos_partner_performance",
        "pos_settle_due",
    ],
    "data": [
        "views/pos_config_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_partner_performance_settle_due/static/src/js/pos_store_patch.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": True,
}
