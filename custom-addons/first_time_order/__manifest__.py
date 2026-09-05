{
    'name': 'First Time Order',
    'summary': 'Guarda la fecha del primer pedido del punto de venta y no la modifica despues',
    'description': """
First Time Order
================
Agrega el campo "First order" (Datetime) al formulario de pedidos del Punto de Venta.
""",
    'version': '19.0.1.0.0',
    'author': 'David Tosse',
    'category': 'Sales/Point of Sale',
    'depends': ['point_of_sale'],
    'images': ['static/description/01_campo_first_order.png'],
    'data': [
        'views/pos_order_form.xml',
    ],
    'license': 'LGPL-3',
    'pre_init_hook': 'pre_init_rename_module',
    'installable': True,
    'application': False,
}
