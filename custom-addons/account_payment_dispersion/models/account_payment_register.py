# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    type_of_account = fields.Selection(
        related='partner_bank_id.co_account_type',
        string='Tipo de cuenta',
    )
    is_colombian_dispersion = fields.Boolean(
        compute='_compute_is_colombian_dispersion',
    )

    @api.depends('payment_method_code')
    def _compute_is_colombian_dispersion(self):
        mapping = self.env['account.payment.method']._get_colombian_dispersion_bank_codes()
        for wizard in self:
            wizard.is_colombian_dispersion = wizard.payment_method_code in mapping

    def _get_dispersion_payment_vals(self, batch_result=None):
        """Extra values copied from this wizard onto account.payment."""
        return {}

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        payment_vals.update({
            key: value
            for key, value in self._get_dispersion_payment_vals(batch_result).items()
            if value
        })
        return payment_vals

    def _create_payment_vals_from_batch(self, batch_result):
        payment_vals = super()._create_payment_vals_from_batch(batch_result)
        payment_vals.update({
            key: value
            for key, value in self._get_dispersion_payment_vals(batch_result).items()
            if value
        })
        return payment_vals
