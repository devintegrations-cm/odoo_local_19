# -*- coding: utf-8 -*-
{
    "name": "POS — Factura Electrónica Cliente DIAN",
    "summary": (
        "Botón en el POS para validar al cliente contra la DIAN (vía Edipo/Jorels) "
        "y asignarlo o crearlo antes de facturar electrónicamente."
    ),
    "description": """
En la pantalla de la orden del POS se agrega un botón "Factura electrónica"
junto al botón nativo de Cliente. El cajero digita tipo y número de documento,
el sistema consulta el adquirente en la DIAN a través del servicio Edipo de
Jorels (el mismo token de la compañía):

- Si la DIAN no confirma el documento, se informa que el cliente debe
  registrarse ante la DIAN y no se asigna nadie.
- Si confirma y el cliente ya existe en Odoo, se asigna tal cual (no se
  pisan sus datos).
- Si confirma y no existe, se crea con los datos que devolvió la DIAN y los
  defaults fiscales que ya usa Jorels; si la DIAN no trajo correo, el popup
  lo pide al cajero.
- Fallo de token o de conexión: se bloquea la asignación con el mensaje
  concreto para distinguirlo de un "no registrado".
""",
    "author": "Libertario Coffee Colombia",
    "website": "https://www.libertariocoffee.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "depends": ["point_of_sale", "l10n_co_edi_jorels"],
    "data": [
        "views/pos_config_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_dian_client/static/src/js/dian_client_popup.js",
            "pos_dian_client/static/src/js/dian_client_button.js",
            "pos_dian_client/static/src/xml/dian_client_popup.xml",
            "pos_dian_client/static/src/xml/dian_client_button.xml",
        ],
    },
    "images": [
        "static/description/01_configuracion.png",
        "static/description/02_boton_producto.png",
        "static/description/03_popup_datos.png",
        "static/description/04_previsualizacion_crear.png",
        "static/description/05_previsualizacion_existente.png",
        "static/description/06_no_registrado.png",
        "static/description/07_tipo_distinto.png",
        "static/description/08_pago_factura.png",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
