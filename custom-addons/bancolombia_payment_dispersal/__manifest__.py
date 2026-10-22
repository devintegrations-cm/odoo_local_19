# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Bancolombia Payment Dispersal',
    'version': '19.0.1.0.2',
    'category': 'Accounting/Localizations',
    'summary': 'Generate Bancolombia payment dispersal Excel files',
    'description': """
        Bancolombia Payment Dispersal
        ==============================

        This module generates payment dispersal files in Excel format for Bancolombia.
        It integrates with Odoo's standard account.batch.payment module to provide:

        * Excel file generation for supplier payments
        * Support for both normal dispersal (220) and payroll (225)
        * Configurable field mapping using safe_eval
        * Multiple transaction types (27, 37, 52, etc.)
        * Automatic validation of payment data

        File Format:
        ------------
        * Header section with company information
        * Configurable columns (12 fields)
        * Support for different payment types

        Requirements:
        -------------
        * Account number must be configured in journal
        * Beneficiary bank accounts required
        * Transaction type must be selected
    """,
    'author': 'Firefly Software Consulting S.A.S',
    'maintainer': 'Firefly Software Consulting S.A.S',
    'website': 'https://firefly-e.com/',
    'depends': [
        'account_payment_dispersion',  # Base Colombian dispersal module
    ],
    "data": [
        # Security
        "security/ir.model.access.csv",

        # Data
        "data/payment_method_data.xml",
        "data/bancolombia_payment_dispersal_field_data.xml",
        "data/res_bank_data.xml",

        # Views
        "views/account_batch_payment_views.xml",
        "views/bancolombia_payment_dispersal_fields_views.xml",
        "views/res_partner_bank_views.xml",
        "views/res_bank_views.xml",
        "views/account_payment_views.xml",
        "views/account_payment_register_views.xml",
        "views/menus.xml",

        # Wizards
        "wizard/bancolombia_set_transaction_type_wizard_views.xml",
    ],
    'images': ['static/description/icon.png'],
    'license': 'OPL-1',
    'countries': ['CO'],
    'application': False,
    'installable': True,
    'auto_install': False,
    'currency': 'USD',
    'price': 50.00,
    'external_dependencies': {
        'python': ['openpyxl']
    },
}
