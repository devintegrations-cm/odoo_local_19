# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    bancodeoccidente_form_of_payment = fields.Selection(
        selection=lambda self: self.env['account.payment']._get_bancodeoccidente_form_of_payment(),
        string='Forma de Pago (Banco Occidente)',
        compute='_compute_bancodeoccidente_register_fields',
        store=True,
        readonly=False,
    )
    bancodeoccidente_type_of_service = fields.Selection(
        selection=lambda self: self.env['account.payment']._get_bancodeoccidente_type_of_service(),
        string='Tipo de Servicio (Banco Occidente)',
        compute='_compute_bancodeoccidente_register_fields',
        store=True,
        readonly=False,
    )

    @api.depends(
        'payment_method_code',
        'partner_bank_id',
        'partner_bank_id.bancodeoccidente_form_of_payment',
        'partner_bank_id.bancodeoccidente_type_of_service',
    )
    def _compute_bancodeoccidente_register_fields(self):
        for wizard in self:
            if wizard.payment_method_code != 'banco_occidente_dispersion':
                wizard.bancodeoccidente_form_of_payment = False
                wizard.bancodeoccidente_type_of_service = False
                continue
            bank = wizard.partner_bank_id
            if not wizard.bancodeoccidente_form_of_payment and bank and bank.bancodeoccidente_form_of_payment:
                wizard.bancodeoccidente_form_of_payment = bank.bancodeoccidente_form_of_payment
            if not wizard.bancodeoccidente_type_of_service and bank and bank.bancodeoccidente_type_of_service:
                wizard.bancodeoccidente_type_of_service = bank.bancodeoccidente_type_of_service

    def _get_dispersion_payment_vals(self, batch_result=None):
        vals = super()._get_dispersion_payment_vals(batch_result)
        if self.payment_method_code != 'banco_occidente_dispersion':
            return vals
        if self.bancodeoccidente_form_of_payment:
            vals['bancodeoccidente_form_of_payment'] = self.bancodeoccidente_form_of_payment
        if self.bancodeoccidente_type_of_service:
            vals['bancodeoccidente_type_of_service'] = self.bancodeoccidente_type_of_service
        return vals
