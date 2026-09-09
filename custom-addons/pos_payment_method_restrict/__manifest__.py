{
    'name': 'POS Payment Method Restrict',
    'version': '19.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Restringe métodos de pago del POS por lista blanca de clientes',
    'description': """
        Permite definir en la configuración de cada POS qué clientes están
        autorizados a usar cada método de pago. Los métodos sin restricción
        siguen disponibles para todos. La configuración es editable incluso
        con la sesión del POS abierta.
    """,
    'author': 'Libertario Coffee',
    'license': 'LGPL-3',
    'depends': ['point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_config_views.xml',
        'views/pos_hotel_report_views.xml',
        'data/pos_order_server_actions.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_payment_method_restrict/static/src/js/payment_restriction_popup.js',
            'pos_payment_method_restrict/static/src/xml/payment_restriction_popup.xml',
            'pos_payment_method_restrict/static/src/js/payment_method_restrict.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
