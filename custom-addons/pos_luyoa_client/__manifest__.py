# -*- coding: utf-8 -*-
{
    "name": "POS — Cliente Luyoa (lealtad)",
    "summary": (
        "Botón en el POS para escanear la tarjeta de lealtad Luyoa del cliente "
        "(QR), consultarlo vía su API y asignarlo o crearlo antes de facturar."
    ),
    "description": """
En la pantalla de la orden del POS se agrega un botón "Luyoa" (junto a
"Nota", en el submenú de los 3 puntos y en la pantalla de pago). El cajero
escanea con la cámara del dispositivo el QR de la tarjeta de lealtad digital
del cliente (Apple/Google Wallet); el sistema consulta el cliente en la API
de Luyoa y lo busca en Odoo:

- Si Luyoa lo confirma y el cliente existe en Odoo (por la tarjeta ya
  vinculada, por correo, o por nombre y teléfono juntos), se asigna a la
  orden y se marca para facturar.
- Si Luyoa lo confirma y no existe en Odoo, se crea con sus datos básicos
  (nombre, correo y teléfono) y se asigna.
- Si el QR no corresponde a un cliente de Luyoa, o falla la credencial o la
  conexión, se informa el motivo concreto y no se asigna nadie.

Solo se identifica por QR (no hay entrada manual de identificadores). Las
cuatro credenciales (URL del API, Integration UID, Business UID y token) se
configuran por punto de venta (entorno demo.luyoa.com, donde está registrado
el negocio) y son obligatorias para usar el botón. Solo el responsable del
POS puede verlas y nunca llegan al navegador: el POS solo llama al servidor.
Las transacciones NO se envían a Luyoa (ver ROADMAP).
""",
    "author": "Libertario Coffee (Miguel Bolivar)",
    "website": "https://libertariocoffee.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.1",
    "license": "LGPL-3",
    "depends": ["point_of_sale"],
    "data": [
        "views/pos_config_view.xml",
    ],
    "images": [
        "static/description/01_configuracion.png",
        "static/description/02_boton_orden.png",
        "static/description/03_cliente_encontrado.png",
        "static/description/04_cliente_nuevo.png",
        "static/description/05_qr_invalido.png",
        "static/description/06_boton_pago.png",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_luyoa_client/static/src/js/luyoa_client_popup.js",
            "pos_luyoa_client/static/src/js/luyoa_client_button.js",
            "pos_luyoa_client/static/src/xml/luyoa_client_popup.xml",
            "pos_luyoa_client/static/src/xml/luyoa_client_button.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
