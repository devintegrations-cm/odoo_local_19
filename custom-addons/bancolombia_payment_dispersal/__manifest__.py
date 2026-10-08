# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Bancolombia Payment Dispersal',
    'version': '19.0.1.0.1',
    'category': 'Localization/Accounting & Finance',
    'description': """
        This module allows you to create an excel file with the necessary information to make the dispersion of payments 
        to suppliers with Bancolombia.
    """,
    'author': 'Firefly Software Consulting S.A.S - (Miguel Bolivar)',
    'maintainer': 'Firefly Software Consulting S.A.S',
    'website': 'https://firefly-e.com/',
    'depends': [
        'account_payment_dispersion'
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/bancolombia_payment_dispersal_field_data.xml",
        "data/res_bank_data.xml",
        "views/account_payment_action_server.xml",
        "views/bancolombia_payment_dispersal_fields_views.xml",
        "views/account_payment_views.xml",
        "views/res_bank_views.xml",
        "views/res_partner_bank_views.xml",
        "views/menus.xml",
        
    ],
    'images': [
        'static/description/01_banco_codigo.png',
        'static/description/02_cuenta_tipo_transaccion.png',
        'static/description/03_diario_cuenta_origen.png',
        'static/description/04_campos_excel_lista.png',
        'static/description/05_campo_excel_formula.png',
        'static/description/06_pago_tipo_transaccion.png',
        'static/description/07_lista_pagos_acciones.png',
        'static/description/08_aviso_validacion.png',
        'static/description/09_dispersion_generada.png',
    ],
    'license': 'OPL-1',
    'application': False,
    'installable': True,
    'currency': 'USD',
    'price': 50.00,
    'external_dependencies': {
        'python': ['openpyxl', 'unidecode']
    },
}
