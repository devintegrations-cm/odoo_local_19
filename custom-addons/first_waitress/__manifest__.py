{
    'name': 'First Waitress',
    'description': 'Adds a "First Waitress" field to the POS order form',
    'version': '19.0.1.0.0',
    'author': 'Osmar Toloza',
    'depends': ['pos_hr'],
    'images': ['static/description/01_campo_first_waitress.png'],
    'data': [
        'views/pos_order_form.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': True,
}
