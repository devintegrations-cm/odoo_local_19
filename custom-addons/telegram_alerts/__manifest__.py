# -*- coding: utf-8 -*-
{
    'name': "Telegram Alerts",

    'summary': """
        Configure and set alerts and action to notify users using telegram""",

    'description': """
        1. Have a preconfigured token access for Telegram Bot
        2. Test connection
        3. Configure related fields with product.template (point of sale > products)
        4. Test Send Cost Difference action
        5. Configure Next Call
    """,

    'author': "Libertario Coffee Roasters",
    'website': "https://www.libertariocoffee.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/19.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Productivity',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'images': [
        'static/description/01_configuracion.png',
        'static/description/02_mensaje_prueba.png',
        'static/description/03_producto.png',
        'static/description/04_acciones_producto.png',
        'static/description/05_accion_planificada.png',
    ],

    # any module necessary for this one to work correctly
    'depends': ['base', 'product'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/telegram_alerts_views.xml',
            'views/product_view.xml',
        'data/telegram_config.xml',
        'data/server_actions.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,

    # 'icon': 'static/description/icon.png',
}
