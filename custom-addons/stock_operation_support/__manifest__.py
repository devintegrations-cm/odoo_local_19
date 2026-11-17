# -*- coding: utf-8 -*-
{
    "name": "Soporte de operaciones de inventario",
    "summary": "Adjunta la remision firmada a una operacion de inventario, la "
               "digitaliza con IA de vision y valida cantidades, partes y firmas",
    "version": "19.0.1.4.2",
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "author": "Libertario Coffee Roasters",
    "website": "https://libertariocoffee.com",
    "depends": [
        "stock",
        "mail",
    ],
    # Sin dependencias Python propias: la IA de vision se llama por HTTP con
    # requests, que ya viene en la imagen de Odoo. Ver README, seccion
    # "Por que requests y no el SDK".
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "views/stock_operation_support_views.xml",
        "views/stock_picking_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
