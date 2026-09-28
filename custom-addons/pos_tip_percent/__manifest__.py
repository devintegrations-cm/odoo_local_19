# -*- coding: utf-8 -*-
{
    'name': "POS Tip Percentage",

    'summary': """
        POS Tip Percentage
    """,

    'description': """
        POS Tip Percentage
    """,

    'author': "Roaya",
    'website': "http://www.roayadm.com",
    'category': 'POS',
    'version': '19.0.1.0.0',
    'depends': ['point_of_sale'],
    'license': 'OPL-1',
    'data': [
        'views/pos_order.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_tip_percent/static/src/js/pos_payment.js',
            'pos_tip_percent/static/src/xml/pos_payment.xml',
        ],
    },
    'images': [
        'static/description/01_configuracion.png',
        'static/description/02_botones_pago.png',
        'static/description/03_propina_aplicada.png',
        'static/description/04_ajuste_pago.png',
        'static/description/05_linea_propina.png',
    ],
    'installable': True,
    'application': False,
}
