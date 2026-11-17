# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'L10n co get superfinanciera dollar exchange rate',
    'version': '19.0.1.0.0',
    'category': 'Localization/Accounting & Finance',
    'description': 'Module that allows us to obtain the dollar exchange rate using the superfinancial service for Colombia.',
    'author': 'Firefly-e',
    'maintainer': 'Firefly-e',
    'website': 'https://firefly-e.com/',
    'depends': [
        'base',
        'l10n_co'
    ],
    'data': [
        'data/get_currency_rate_usd_to_cop_ir_cron.xml',
        'views/res_company_views.xml',
    ],
    'license': 'LGPL-3',
    'application': False,
    'installable': True
}