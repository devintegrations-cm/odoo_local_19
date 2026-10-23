# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    bancolombia_payment_type = fields.Selection(
        selection=[
            ('220', 'Proveedores (220)'),
            ('225', 'Nómina (225)'),
        ],
        string='Tipo de Dispersión (Bancolombia)',
        compute='_compute_bancolombia_register_fields',
        store=True,
        readonly=False,
    )
    bancolombia_type_of_transaction = fields.Selection(
        selection=lambda self: self.env['account.payment']._get_bancolombia_type_of_transaction(),
        string='Tipo de Transacción Bancolombia',
        compute='_compute_bancolombia_register_fields',
        store=True,
        readonly=False,
    )

    @api.depends(
        'payment_method_code',
        'partner_type',
        'partner_bank_id',
        'partner_bank_id.bancolombia_type_of_transaction',
        'partner_bank_id.co_account_type',
    )
    def _compute_bancolombia_register_fields(self):
        for wizard in self:
            if wizard.payment_method_code != 'bancolombia_dispersion':
                wizard.bancolombia_payment_type = False
                wizard.bancolombia_type_of_transaction = False
                continue

            if not wizard.bancolombia_payment_type:
                if self.env['account.payment']._is_payroll_dispersion_context():
                    wizard.bancolombia_payment_type = '225'
                else:
                    wizard.bancolombia_payment_type = (
                        '220' if wizard.partner_type == 'supplier' else '225'
                    )

            if wizard.bancolombia_type_of_transaction:
                continue
            bank = wizard.partner_bank_id
            if bank and bank.bancolombia_type_of_transaction:
                wizard.bancolombia_type_of_transaction = bank.bancolombia_type_of_transaction
            elif bank and bank.co_account_type == 'current_account':
                wizard.bancolombia_type_of_transaction = '27'
            elif bank and bank.co_account_type == 'savings_account':
                wizard.bancolombia_type_of_transaction = '37'
            # Sin tipo de cuenta queda vacío: no se inventa el tipo.

    def _get_dispersion_payment_vals(self, batch_result=None):
        vals = super()._get_dispersion_payment_vals(batch_result)
        if self.payment_method_code != 'bancolombia_dispersion':
            return vals
        if self.bancolombia_payment_type:
            vals['bancolombia_payment_type'] = self.bancolombia_payment_type
        if self.bancolombia_type_of_transaction:
            vals['bancolombia_type_of_transaction'] = self.bancolombia_type_of_transaction
        return vals
