# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Account Payment Dispersal',
    'version': '19.0.1.0.0',
    'category': 'Localization/Accounting & Finance',
    'description': 'This module allows to visualise the different dispersions that have been carried out over time..',
    'author': 'Firefly Software Consulting S.A.S',
    'maintainer': 'Firefly Software Consulting S.A.S',
    'website': 'https://firefly-e.com/',
    'depends': [
        'account',
        'l10n_co'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/res_bank_data.xml',
        'views/account_payment_views.xml',
        'views/res_bank_views.xml',
        'views/account_payment_dispersal_views.xml',
        'views/res_partner_bank_views.xml',
        'views/res_partner_views.xml',
        'views/menus.xml'
    ],
    'images': [
        'static/description/01_banco_codigo.png',
        'static/description/02_cuenta_bancaria_tipo.png',
        'static/description/03_lista_cuentas_bancarias.png',
        'static/description/04_pago_proveedor_tipo_cuenta.png',
        'static/description/05_menu_dispersiones.png',
        'static/description/06_menu_configuracion.png',
        'static/description/07_formulario_dispersion.png',
    ],
    'license': 'OPL-1',
    'application': False,
    'installable': True,
    'currency': 'USD',
    'price': 20.00,

}
