{
    "name": "Pos Cash In/Out Message",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "summary": "Display a configurable message and confirmation popup in the Cash In/Out popup",
    "description": """
POS Cash In/Out Message
=======================

Adds a configurable plain-text message and a confirmation popup to the Cash
In/Out workflow in the Point of Sale interface.

Features:

* Configurable message shown in the confirmation popup.
* Confirmation popup before registering any cash movement.
* Shows movement type (in/out), amount, and the last-movement warning.
* Touch-friendly design.
""",
    "author": "Miguel Bolivar, Libertario Coffee",
    "website": "https://www.libertariocoffee.com",
    "license": "LGPL-3",
    "depends": [
        "pos_closing_validation",
    ],
    "data": [
        "views/pos_config_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_cash_in_out_message/static/src/css/cash_move_confirm_popup.css",
            "pos_cash_in_out_message/static/src/js/cash_move_confirm_popup.js",
            "pos_cash_in_out_message/static/src/xml/cash_move_confirm_popup.xml",
            "pos_cash_in_out_message/static/src/js/cash_move_popup_patch.js",
        ],
    },
    "installable": True,
    "application": False,
}
