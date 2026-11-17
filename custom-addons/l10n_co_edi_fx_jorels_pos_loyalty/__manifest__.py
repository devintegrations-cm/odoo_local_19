# -*- coding: utf-8 -*-
{
    'name': "Fix EI Jorels with POS Loyalty Redemptions",

    'summary': """
        Fixes Colombian electronic invoicing (Jorels) integration with POS loyalty rewards""",

    'description': """
        This module handles reward line processing, tax calculations, and enforces 
        mandatory invoice fields for Colombian electronic invoicing compliance in POS.
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    'category': 'Point of Sale',
    'version': '19.0.1.0.4',

    # any module necessary for this one to work correctly
    'depends': ['pos_loyalty', 'l10n_co_edi_jorels', 'l10n_co_edi_jorels_pos'],

    # always loaded
    'data': [
        'views/account_move_view.xml',
        'views/pos_res_config_settings_view.xml',
        'views/report_invoice_priority.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'l10n_co_edi_fx_jorels_pos_loyalty/static/src/js/models.js',
            'l10n_co_edi_fx_jorels_pos_loyalty/static/src/js/payment_screen.js',
            'l10n_co_edi_fx_jorels_pos_loyalty/static/src/js/order_payment_validation.js',
        ]
    },
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
