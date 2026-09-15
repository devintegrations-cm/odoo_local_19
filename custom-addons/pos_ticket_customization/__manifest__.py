{
    'name': 'POS - Información adicional en el ticket',
    'version': '19.0.1.1.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Bloques configurables por tienda en el ticket del POS: texto, QR, códigos de barras, WiFi, reseñas, vCard.',
    'description': """
Permite configurar, por punto de venta, N bloques de información adicional que se
imprimen en el ticket del POS (cabecera, antes del pie o al final).

Tipos soportados: texto libre, texto legal, separador, imagen, QR de URL, QR de texto
arbitrario, código de barras, QR de reseña de Google, QR de WhatsApp, QR de WiFi,
QR de contacto (vCard) y QR de pago.

Los QR y códigos de barras se generan con el endpoint nativo `/report/barcode`
(ReportLab); no se usa ninguna librería JavaScript de terceros. Las imágenes se
incrustan en el ticket como `data:` URI, de modo que se siguen imprimiendo aunque
la caja pierda la conexión con el servidor; si aun así alguna no se puede generar,
el bloque imprime la misma información en texto (SSID y clave del WiFi, la URL,
el teléfono...) en lugar de dejar un hueco en blanco.
""",
    'author': 'Libertario Coffee',
    'website': 'https://libertariocoffee.com',
    'license': 'LGPL-3',
    'depends': ['point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'security/pos_receipt_custom_block_rules.xml',
        'views/pos_receipt_custom_block_views.xml',
        'views/pos_config_view.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_ticket_customization/static/src/utils/receipt_block_utils.js',
            'pos_ticket_customization/static/src/app/services/pos_store.js',
            'pos_ticket_customization/static/src/app/services/printer_service.js',
            'pos_ticket_customization/static/src/app/screens/receipt_screen/receipt_screen.js',
            'pos_ticket_customization/static/src/app/screens/receipt_screen/receipt/order_receipt.js',
            'pos_ticket_customization/static/src/app/screens/receipt_screen/receipt/order_receipt.scss',
            'pos_ticket_customization/static/src/app/screens/receipt_screen/receipt/order_receipt.xml',
        ],
        # Los tests unitarios cubren `receipt_block_utils.js`, que no depende del
        # POS (solo de `_t`), así que se puede cargar suelto en el bundle de tests
        # y probar sus funciones sin montar una sesión de caja.
        'web.qunit_suite_tests': [
            'pos_ticket_customization/static/src/utils/receipt_block_utils.js',
            'pos_ticket_customization/static/tests/receipt_block_utils_tests.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
