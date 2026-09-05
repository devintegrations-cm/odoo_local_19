# -*- coding: utf-8 -*-
{
    'name': "POS Limit Products",
    'summary': """
        Choose in product which pos to be added to
        """,
    'author': "Roaya",
    'website': "https://www.roayadm.com",
    'category': 'Point of sale',
    'license': 'OPL-1',
    'version': '19.0.1.0.0',
    "depends": ["point_of_sale"],
    "assets": {
        "point_of_sale._assets_pos": [
            "ro_pos_limit_products/static/src/app/services/pos_store.js",
        ],
    },
    "data": [
        "views/product.xml"
    ],
    'images': [
        'static/description/01_configuracion.png',
        'static/description/02_pos_antes.png',
        'static/description/03_pos_filtrado.png',
    ],
}
