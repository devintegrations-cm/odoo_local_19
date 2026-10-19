{
    'name': 'POS - Configuración de comanda',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Ajusta el espaciado, el encabezado y los textos de la comanda de preparación del POS.',
    'author': 'Miguel Bolivar, Libertario Coffee',
    'website': 'https://libertariocoffee.com',
    'license': 'LGPL-3',
    'depends': ['point_of_sale'],
    'data': [
        'views/pos_config_view.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_comanda_config/static/src/app/services/pos_store.js',
            'pos_comanda_config/static/src/app/store/order_change_receipt.xml',
        ],
    },
    'images': [
        'static/description/01_configuracion.png',
        'static/description/02_comanda_por_defecto.png',
        'static/description/03_comanda_opciones.png',
        'static/description/04_comanda_etiquetas_core.png',
        'static/description/05_comanda_espaciado.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
