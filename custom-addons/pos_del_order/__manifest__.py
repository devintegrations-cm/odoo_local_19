# -*- coding: utf-8 -*-
{
    'name': "Delete Pos Order",

    'summary': """
        Restricts which employees can delete orders in the Point of Sale
    """,

    'description': """
        Shows or hides the delete-order icon depending on the employees allowed
        on the point of sale, and refuses the deletion for the others. The rule is
        enforced in the POS store, so it also covers the delete button of the
        product screen. Leave the list empty to allow every employee.
    """,

    'author': "Osmar Toloza",
    'website': "desarrollo@libertariocoffee.com",
    'category': 'Sales/Point of Sale',
    'version': '19.0.1.0.0',
    'depends': ['base', 'point_of_sale', 'pos_hr'],
    'license': 'OPL-1',
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'images': [
        'static/description/01_configuracion.png',
        'static/description/02_ordenes_autorizado.png',
        'static/description/03_ordenes_no_autorizado.png',
        'static/description/04_cancelar_denegado.png',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_del_order/static/src/app/services/pos_store.js',
            'pos_del_order/static/src/app/screens/ticket_screen/ticket_screen.js',
        ],
    },
    'installable': True,
    'auto_install': False,
}
