# -*- coding: utf-8 -*-
{
    'name': "Obligatory Invoice",

    'summary': """
        When the PaymentScreen is open, set invoice obligatory
    """,

    'description': """
        Cuando el flag `enable_obin` del punto de venta esta activo, todo pedido
        sale facturado: al entrar a la pantalla de pago se marca "Facturar" y no
        se puede desmarcar.
    """,

    'author': "Osmar Toloza",
    'website': "desarrollo@libertariocoffee.com",
    'category': 'POS',
    'version': '19.0.1.0.0',
    'depends': ['point_of_sale'],
    'license': 'OPL-1',
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'images': [
        'static/description/01_configuracion.png',
        'static/description/02_pantalla_pago.png',
        'static/description/03_no_se_puede_desmarcar.png',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_obligatory_invoice/static/src/js/Screens/PaymentScreen.js',
        ]
    },
    'installable': True,
    'auto_install': True,
}
