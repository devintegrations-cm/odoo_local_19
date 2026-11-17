{
    "name": "Validador de costos de compra",
    "version": "19.0.1.1.1",
    "category": "Purchases",
    "summary": "Colorea y avisa cuando un precio de compra no cuadra con lo que cuesta el producto, y retiene la recepción para el revisor",
    "description": """
Validador de costos de compra
=============================

Evita que un error de digitación (precio, cantidad o unidad de medida) entre al costo del inventario.

- Cada línea de compra se compara, en la misma unidad de medida, con lo que suele costar el producto: la mediana
  de sus últimas compras o, si no tiene, su costo actual. La tolerancia es la "Variación de Costo" del producto
  (módulo purchase_price_validation).
- Amarillo: fuera de la tolerancia. Rojo: precio en cero o desfase incoherente (por defecto más del doble o menos
  de la mitad, como 20 leches por $1.000.000 o una caja digitada como unidad). Aviso discreto, no bloquea la orden.
- Al recibir, si sigue en rojo (o se recibe mucho más de lo pedido), la recepción queda marcada, se avisa al revisor
  de compras por correo o bandeja de Odoo con una actividad, y opcionalmente se retiene hasta que él la apruebe.

Solo revisa lo nuevo: las órdenes creadas antes de la fecha de arranque (por defecto, la fecha de instalación) y
sus recepciones siguen exactamente igual. Nunca modifica un costo.

No depende de purchase_price_validation ni lo modifica: lleva su propio margen de variación por producto (el mismo campo, con el mismo valor por defecto), así que se instala y se desinstala por separado.
""",
    "author": "Libertario Coffee Roasters",
    "website": "https://www.libertariocoffee.com",
    "license": "LGPL-3",
    "depends": ["purchase_stock", "stock_account", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "views/purchase_order_views.xml",
        "views/stock_picking_views.xml",
        "views/product_template_views.xml",
        "views/cost_review_wizard_views.xml",
        "views/cost_validator_config_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {"web.assets_backend": ["purchase_cost_validator/static/src/scss/cost_validator.scss"]},
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
