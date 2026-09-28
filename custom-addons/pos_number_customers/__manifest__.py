# -*- coding: utf-8 -*-
{
    'name': "Ask Number of Customers",

    'summary': """
        Asks for the number of customers of the order when entering the payment screen
    """,

    'description': """
        When the payment screen is opened, the cashier is asked for the number of
        customers, within the minimum and maximum configured per point of sale,
        before any payment is processed.  If the prompt is dismissed, the count
        is still required at validation, so the requirement cannot be skipped.
        The value is stored as the customer count of the order (the same one used
        by the restaurant tables), so tickets and reports keep working.
    """,

    'author': "Libertario Coffee Roasters",
    'website': "https://www.libertariocoffee.com",
    'category': 'Sales/Point of Sale',
    'version': '19.0.1.0.0',
    'depends': ['pos_restaurant'],
    'license': 'LGPL-3',
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'images': [
        'static/description/01_configuracion.png',
        'static/description/02_pregunta_al_pagar.png',
        'static/description/03_fuera_de_rango.png',
        'static/description/04_pregunta_al_validar.png',
        'static/description/05_resultado.png',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_number_customers/static/src/app/utils/order_payment_validation.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
