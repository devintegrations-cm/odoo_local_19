# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class AccountPayment(models.Model):

    _inherit = 'account.payment'

    type_of_account = fields.Selection(
        related="partner_bank_id.co_account_type",
        string='Tipo de cuenta',
    )
    is_colombian_dispersion = fields.Boolean(
        compute='_compute_is_colombian_dispersion',
    )

    @api.depends('payment_method_code')
    def _compute_is_colombian_dispersion(self):
        mapping = self.env['account.payment.method']._get_colombian_dispersion_bank_codes()
        for payment in self:
            payment.is_colombian_dispersion = payment.payment_method_code in mapping

    def _is_payroll_dispersion_context(self):
        """True when the payment comes from the Colombian payroll run wizard."""
        return bool(
            self.env.context.get('hr_payroll_payment_register')
            or self.env.context.get('dispersion_purpose') == 'payroll'
        )

    def _get_dispersion_batch_grouping_key(self):
        """Extra key so one batch only contains one dispersal service type.

        Bank modules override this (e.g. Davivienda NOMI/PROV, Bancolombia 220/225).
        """
        self.ensure_one()
        return False

    def create_batch_payment(self):
        """Create one batch per journal, method and dispersal service type."""
        valid_payment_states = self.env['account.batch.payment']._valid_payment_states()
        if any(payment.state not in valid_payment_states for payment in self):
            return super().create_batch_payment()

        groups = {}
        for payment in self:
            key = (
                payment.journal_id.id,
                payment.payment_method_id.id,
                payment.payment_type,
                payment._get_dispersion_batch_grouping_key(),
            )
            groups.setdefault(key, self.browse())
            groups[key] |= payment

        if len(groups) <= 1:
            return super().create_batch_payment()

        batches = self.env['account.batch.payment']
        for payments in groups.values():
            action = payments.create_batch_payment()
            if action.get('res_id') and action.get('res_model') == 'account.batch.payment':
                batches |= self.env['account.batch.payment'].browse(action['res_id'])
            elif action.get('res_model') == 'account.create.batch.error.wizard':
                # No dejar lotes huérfanos: si un grupo posterior falla, los
                # lotes ya creados se revierten antes de mostrar el error, y
                # el usuario reintenta con todos los grupos una vez corregido.
                batches.unlink()
                return action

        return {
            'name': _('Pagos por lotes'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.batch.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', batches.ids)],
            'context': {'create': False},
        }
