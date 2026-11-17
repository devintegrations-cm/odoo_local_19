# -*- coding: utf-8 -*-
{
    'name': "POS IP CAMERA CAPTURE",

    'summary': """
        Capture, save and a ip camera image
        """,

    'description': """
        Configure a ip camera in POS to save an image when the payment button is actioned
    """,

    'author': "Libertario Coffee Rosters",
    'website': "https://libertariocoffee.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/19.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Point of Sale',
    'version': '19.0.1.0.1',

    # any module necessary for this one to work correctly
    'depends': ['point_of_sale'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/pos_order.xml',
        'views/face_details_views.xml',

    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_ip_cam_capture/static/src/app/services/pos_store.js',
        ],
    },
    'license': 'LGPL-3',
}
