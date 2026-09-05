# -*- coding: utf-8 -*-
{
    'name': "POS popup Validation Number",

    'summary': """
        Opens a Popup Validation Number
    """,

    'description': """
        Whe the cashiers uses validation button in Payment Screen, gets the validation number.
        When the payment is card.
    """,

    'author': "Osmar Toloza",
    'website': "desarrollo@libertariocoffee.com",
    'category': 'POS',
    'version': '19.0.1.0.0',
    'depends': ['base', 'point_of_sale', 'account_accountant'],
    'license': 'OPL-1',
    'data': [
        # 'security/ir.model.access.csv',
        'views/pos_order.xml',
        'views/pos_payment.xml',
        'views/pos_payment_method.xml',
        'views/account_move_line_list.xml',
    ],
    'images': [
        'static/description/01_configuracion.png',
        'static/description/02_pos_dialogo.png',
        'static/description/03_pos_lineas.png',
        'static/description/04_backend_pedido.png',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_voucher_num/static/src/app/*',
        ],
    },
    'auto_install': True,
}
