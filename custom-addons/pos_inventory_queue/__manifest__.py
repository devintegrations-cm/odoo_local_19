{
    'name': 'Pos Inventory Queue',
    'version': '19.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Serializes POS real-time inventory operations to prevent concurrency',
    'description': """
        When multiple POS terminals invoice simultaneously with real-time inventory,
        the system processes stock.quant updates concurrently causing deadlocks and
        race conditions.

        This module intercepts the picking creation flow for POS real-time pickings
        and serializes their processing through a persistent queue using
        PostgreSQL FOR UPDATE SKIP LOCKED for atomic claim.
    """,
    "author": "Miguel Bolivar, Libertario Coffee",
    "website": "https://www.libertariocoffee.com",
    "license": "LGPL-3",
    'depends': ['point_of_sale'],
    'data': [
        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        'data/ir_config_parameter.xml',
        'security/ir.model.access.csv',
        'views/pos_inventory_queue_views.xml',
        'views/inventory_queue_config_views.xml',
    ],
    'images': [
        'static/description/01_menu_configuracion.png',
        'static/description/02_configuracion.png',
        'static/description/03_cola_de_inventario.png',
        'static/description/04_cola_procesados.png',
        'static/description/05_item_fallido.png',
        'static/description/06_item_procesado.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
