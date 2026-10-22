# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class AccountPaymentMethod(models.Model):
    _inherit = 'account.payment.method'

    @api.model
    def _get_colombian_dispersion_bank_codes(self):
        res = super()._get_colombian_dispersion_bank_codes()
        res['bancolombia_dispersion'] = {
            'codes': ('1007',),
            'bic_prefixes': ('COLOCOBM',),
            'name_fragments': ('BANCOLOMBIA',),
        }
        return res
