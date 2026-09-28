{
    'name': 'Purchase Order Price Validation',
    'version': '19.0.1.1.0',
    'category': 'Purchases',
    'summary': 'Validación del precio unitario en órdenes de compra y movimientos de inventario',
    'description': """
        Este módulo valida las siguientes condiciones:
        - Validar la variación del precio unitario con respecto al costo y compararla con la variación establecida en el producto
        - Validar que el precio unitario no sea igual a 0
        - Aplica validaciones tanto en órdenes de compra como en movimientos de inventario
    """,
    'author': "Libertario Coffee Roasters",
    'website': "https://www.libertariocoffee.com",
    'license': 'LGPL-3',
    'depends': ['purchase', 'product', 'stock'],
    'images': [
        'static/description/01_configuracion.png',
        'static/description/02_producto.png',
        'static/description/03_orden_compra.png',
        'static/description/04_recepcion.png',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_order_views.xml',
        'views/product_template_views.xml',
        'views/confirmation_variation_wizard.xml',
        'views/warning_variation_wizard.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
}