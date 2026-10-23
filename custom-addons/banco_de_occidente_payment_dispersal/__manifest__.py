# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Banco de Occidente Payment Dispersal',
    'version': '19.0.1.0.3',
    'category': 'Accounting/Localizations',
    'summary': 'Generate Banco de Occidente payment dispersal TXT files',
    'description': """
        Banco de Occidente Payment Dispersal
        =====================================

        This module generates payment dispersal files in TXT format (fixed-width)
        for Banco de Occidente. It integrates with Odoo's standard
        account.batch.payment module to provide:

        * TXT file generation with fixed-width format
        * Configurable field mapping using safe_eval
        * Support for different payment forms (cheque, cash, credit)
        * Automatic validation of payment data
        * Service types (notice, control, both)

        File Format:
        ------------
        * Fixed-width TXT file (199 positions, same format as the Odoo 17
          generator; compare against a historical file accepted by the bank)
        * Header record (type 1)
        * Detail records (type 2) - one per payment
        * Footer record (type 3)
        * LF line endings, including after the last line (same as v17)
        * Overflows of identifier fields (account numbers, documents) are
          reported as errors instead of being silently truncated

        Requirements:
        -------------
        * Account number must be configured in journal
        * Beneficiary bank accounts required
        * Payment form must be selected
        * Account type (Ahorros/Corriente) required
    """,
    'author': 'Firefly Software Consulting S.A.S',
    'maintainer': 'Firefly Software Consulting S.A.S',
    'website': 'https://firefly-e.com/',
    'depends': [
        'account_payment_dispersion',  # Base Colombian dispersal module
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',

        # Data
        'data/payment_method_data.xml',
        'data/bancodeoccidente_payment_dispersal_field_data.xml',

        # Views
        'views/account_batch_payment_views.xml',
        'views/account_payment_views.xml',
        'views/account_payment_register_views.xml',
        'views/account_payment_action_server.xml',
        'views/bancodeoccidente_payment_dispersal_fields_views.xml',
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
    'price': 50.00,
}