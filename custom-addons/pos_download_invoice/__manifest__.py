# -*- coding: utf-8 -*-
{
    'name': "POS Download Invoice",

    'summary': """
        This module creates a check to enable downloading PDF POS invoices.""",

    'description': """
        Enable a checkbox to enable/disable downloading PDF POS invoices.
    """,

    'author': "Desarrollo Libertario",
    'support':'regionalit@libertariocoffee.com',

    'category': 'POS',
    'version': '19.0.1.0.0',

    'depends': ['point_of_sale'],
    'license': 'LGPL-3',
    'images': [
        'static/description/01_configuration.png',
        'static/description/02_payment_screen.png',
    ],

    'data': [
        'views/pos_res_config_settings_view.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_download_invoice/static/src/app/utils/order_payment_validation.js',
        ]
    },
}
