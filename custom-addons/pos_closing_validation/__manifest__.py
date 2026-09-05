{
    "name": "Pos Closing Validation",
    "version": "19.0.0.0.0",
    "category": "Sales/Point of Sale",
    "summary": "Controls POS cash movements and session closing",
    "description": """
POS Closing Validation
======================

Extends the standard Odoo Point of Sale cash control workflow with:

* Configurable maximum Cash In/Out movements per POS.
* Backend validation of the cash movement limit.
* Idempotent Cash In/Out requests, so a connection retry cannot register the
  same movement twice.
* Cash In/Out blocked on rescue sessions (backend + frontend).
* Last-movement warning and movement counter in the Cash In/Out popup.
* Maximum authorized cash difference validation when closing a session.
* Blocking new session opening when rescue sessions are pending.
* Unified closing snapshot (single source of truth, reconciled against Odoo's
  own theoretical closing balance).
* Transactional closing with a bounded row-level lock to prevent race
  conditions and hanging terminals.
* Enhanced closing popup with an explicit expected cash summary.
* Internal consistency checks that block a cashier but only warn a manager, so
  a false positive cannot trap a store at closing time.
""",
    "author": "Miguel Bolivar, Libertario Coffee",
    "website": "https://www.libertariocoffee.com",
    "license": "LGPL-3",
    "depends": [
        "point_of_sale",
    ],
    "data": [
        "views/pos_config_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_closing_validation/static/src/js/pos_store_patch.js",
            "pos_closing_validation/static/src/js/cash_move_popup_patch.js",
            "pos_closing_validation/static/src/js/cash_move_list_popup_patch.js",
            "pos_closing_validation/static/src/xml/cash_move_popup.xml",
            "pos_closing_validation/static/src/xml/closing_popup_extension.xml",
        ],
    },
    "installable": True,
    "application": False,
}
