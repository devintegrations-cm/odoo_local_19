# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class AccountPaymentMethod(models.Model):
    _inherit = 'account.payment.method'

    @api.model
    def _get_colombian_dispersion_bank_codes(self):
        res = super()._get_colombian_dispersion_bank_codes()
        res['banco_occidente_dispersion'] = {
            'codes': ('1023',),
            'bic_prefixes': ('OCCICOBC',),
            'name_fragments': ('OCCIDENTE',),
        }
        return res
