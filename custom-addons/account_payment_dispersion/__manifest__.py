# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Account Payment Dispersal - Colombia',
    'version': '19.0.1.0.4',
    'category': 'Accounting/Localizations',
    'summary': 'Base module for Colombian bank payment dispersal files',
    'description': """
        Base module for Colombian Bank Payment Dispersal
        ==================================================

        This module provides the base infrastructure for generating bank payment
        dispersal files for Colombian banks. It integrates with Odoo's standard
        account.batch.payment module to provide:

        * Colombian-specific bank account types (Ahorros, Corriente)
        * Bank configuration for Colombian entities
        * Base framework for payment method implementations
        * Standard validation and error handling

        This module is designed to be extended by bank-specific modules like:
        * bancolombia_payment_dispersal
        * banco_de_occidente_payment_dispersal
        * And others...
    """,
    'author': 'Firefly Software Consulting S.A.S',
    'maintainer': 'Firefly Software Consulting S.A.S',
    'website': 'https://firefly-e.com/',
    'depends': [
        'account',
        'account_batch_payment',  # Enterprise module required
        'l10n_co',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',

        # Data
        'data/res_bank_data.xml',

        # Views
        'views/account_batch_payment_views.xml',
        'views/account_payment_dispersal_views.xml',
        'views/account_payment_views.xml',
        'views/account_payment_register_views.xml',
        'views/res_bank_views.xml',
        'views/res_partner_bank_views.xml',
        'views/menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'license': 'OPL-1',
    'countries': ['CO'],
    'application': False,
    'installable': True,
    'auto_install': False,
    'currency': 'USD',
    'price': 20.00,
}
