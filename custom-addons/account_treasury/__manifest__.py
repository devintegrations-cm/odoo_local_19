# -*- coding: utf-8 -*-
{
    'name': "Account treasury",

    'summary': """
        Notificacion por correo de pagos a proveedores, con solicitantes en la orden de compra
    """,

    'description': """
Tesoreria: notificacion de pagos a proveedores.

- Avisa por correo al proveedor cuando se registra un pago, con el detalle de las facturas.
- Permite indicar en la orden de compra a quien mas hay que notificar (solicitantes).
- Muestra en la factura de proveedor quien la solicito.
- Agrega al asistente de registro de pagos la opcion de enviar el aviso al confirmar.
    """,

    'author': "Osmar Toloza",
    'website': "desarrollo@libertariocoffee.com",
    'category': 'Accounting',
    'version': '19.0.1.0.0',
    'depends': ['base','account','purchase','contacts'],
    'license': 'OPL-1',
    'sequence':10,
    'images': [
        'static/description/01_configuracion_orden_compra.png',
        'static/description/02_asistente_de_pago.png',
        'static/description/03_pago_notificado.png',
        'static/description/04_factura_solicitantes.png',
    ],
    'data': [
        # Desactivadas desde 17: dependen de `bank_account_type_col`, cuyo modelo
        # (models/res_partner_bank.py) tambien esta desactivado en models/__init__.py.
        # Ademas en 19 `account.view_partner_property_form` ya no expone `acc_number`
        # (usa el widget many2many_tags_banks), asi que views/res.partner.xml
        # NO matchearia. Ver informe de migracion antes de reactivarlas.
        #"views/res.partner.bank.xml",
        #"views/res.partner.xml",
        "views/account.move.view.fom.xml",
        "views/account.payment.xml",
        "views/purchase_order_form_requester.xml",
        "data/mail_template.xml",
        "data/request_mail_template.xml",
        "wizard/account_payment_register_views.xml",
    ],
    #'assets': {
    #    'point_of_sale.assets': [
    #        'pos_del_order/static/src/xml/Screens/TicketScreen.xml',
    #        'pos_del_order/static/src/js/Screens/TicketScreen.js',
    #       
    #    ],
    #},
    #'installable': True,
    #'application': True,
    'auto_install': True,
}
