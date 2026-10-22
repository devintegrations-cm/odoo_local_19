# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResPartnerBank(models.Model):
    """
    Extension of res.partner.bank for Bancolombia-specific fields.

    Adds transaction type field that can be configured per bank account
    and used as default for payments.
    """
    _inherit = 'res.partner.bank'

    @api.model
    def _get_bancolombia_type_of_transaction(self):
        return self.env['account.payment']._get_bancolombia_type_of_transaction()

    bancolombia_type_of_transaction = fields.Selection(
        selection='_get_bancolombia_type_of_transaction',
        string='Tipo de Transacción Bancolombia',
        help='Tipo de transacción predeterminado para pagos Bancolombia con esta cuenta'
    )
