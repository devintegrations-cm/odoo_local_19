{
    'name': 'POS API Credibanco',
    'version': '19.0.1.0.0',
    'summary': 'Integration of the payment terminal with the Credibanco API in the POS.',
    'description': '''
Credibanco Payment Terminal Integration
=======================================

Payment processing against a Credibanco terminal attached to the point of
sale:

* Card payment through the terminal over WebSocket.
* Transaction cancellation (registered as a compensating movement).
* Recovery mechanism for transactions left without a final response.
* Extra terminal information stored per payment, and manual completion by a
  POS manager.
''',
    'author': "Libertario Coffee Roasters",
    'website': "https://www.libertariocoffee.com",
    'category': 'Sales/Point of Sale',
    'depends': ['point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_payment_method_credibanco_views.xml',
        'views/pos_payment_views_credibanco.xml',
        'views/pos_settings_credibanco.xml',
        'wizard/credibanco_extra_info_wizard.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            # Protocol and transport first: the terminal interface imports both,
            # and it is what register_payment_method plugs into the core.
            'pos_api_credibanco/static/src/app/utils/payment/credibanco_protocol.js',
            'pos_api_credibanco/static/src/app/utils/payment/credibanco_transport.js',
            'pos_api_credibanco/static/src/app/components/popups/text_list_popup/text_list_popup.js',
            'pos_api_credibanco/static/src/app/components/popups/text_list_popup/text_list_popup.xml',
            'pos_api_credibanco/static/src/app/utils/payment/credibanco_terminal.js',
            'pos_api_credibanco/static/src/app/screens/payment_screen/payment_screen.js',
            'pos_api_credibanco/static/src/css/notification_override.css',
            'pos_api_credibanco/static/src/css/text_list_popup.css',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
