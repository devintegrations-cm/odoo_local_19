# -*- coding: utf-8 -*-
{
    'name': "Restrict erase POS order line",

    'summary': """
        Set a list of employes able to delete POS order lines
        """,

    'description': """
        In POS cofiguration set a list of employes able to delete POS order lines
    """,

    'author': "Libertario Coffee Roasters",
    'website': "https://www.libertariocoffee.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/17.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Point of Sale',
    'version': '19.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['pos_restaurant'],

    'images': [
        'static/description/01_configuracion.png',
        'static/description/02_linea_enviada.png',
        'static/description/03_reduccion_denegada.png',
        'static/description/04_reduccion_autorizada.png',
    ],

    # always loaded
    'data': [
        'views/pos_order_view.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_restrict_del_ordered_order_line/static/src/js/models.js',
            'pos_restrict_del_ordered_order_line/static/src/js/pos_store.js',
            'pos_restrict_del_ordered_order_line/static/src/js/split_bill_screen.js',
            'pos_restrict_del_ordered_order_line/static/src/js/orderline.js',
            'pos_restrict_del_ordered_order_line/static/src/xml/orderline.xml',
            'pos_restrict_del_ordered_order_line/static/src/css/orderline.scss',
        ],
    },
    'application': False,
    'installable': True,
    'license': 'LGPL-3',
}
