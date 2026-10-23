# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BancolombiaSetTransactionTypeWizard(models.TransientModel):
    _name = 'bancolombia.set.transaction.type.wizard'
    _description = 'Wizard para configurar tipo de transacción Bancolombia en masa'

    @api.model
    def _get_bancolombia_type_of_transaction(self):
        return self.env['account.payment']._get_bancolombia_type_of_transaction()

    bancolombia_type_of_transaction = fields.Selection(
        selection='_get_bancolombia_type_of_transaction',
        string='Tipo de Transacción Bancolombia',
        required=True,
        default='37',
        help='Tipo de transacción que se aplicará a todos los pagos seleccionados'
    )

    also_set_in_bank_account = fields.Boolean(
        string='También configurar en cuenta bancaria',
        default=True,
        help='Si se activa, también configurará el tipo de transacción en la cuenta bancaria del beneficiario como valor por defecto'
    )

    payment_count = fields.Integer(
        string='Número de Pagos',
        compute='_compute_payment_count'
    )

    @api.depends_context('active_ids')
    def _compute_payment_count(self):
        for wizard in self:
            wizard.payment_count = len(self.env.context.get('active_ids', []))

    def action_set_transaction_type(self):
        """Aplica el tipo de transacción a los pagos seleccionados"""
        self.ensure_one()

        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            raise UserError(_('No hay pagos seleccionados.'))

        payments = self.env['account.payment'].browse(active_ids)

        # Validar que los pagos son outbound y de banco
        invalid_payments = payments.filtered(
            lambda p: p.payment_type != 'outbound' or p.journal_id.type != 'bank'
        )
        if invalid_payments:
            raise UserError(_(
                'Solo se puede configurar el tipo de transacción para pagos salientes (outbound) de tipo bancario. '
                'Los siguientes pagos no cumplen este criterio: %s',
                ', '.join(invalid_payments.mapped('name')),
            ))

        # Solo pagos aún no pagados: en los pagados el tipo de transacción es
        # el dato con el que se generó un archivo que el banco ya procesó.
        closed_payments = payments.filtered(
            lambda p: p.state not in ('draft', 'in_process')
        )
        if closed_payments:
            raise UserError(_(
                'Solo se puede cambiar el tipo de transacción en pagos en borrador o en proceso. '
                'Los siguientes pagos ya están cerrados: %s',
                ', '.join(closed_payments.mapped('name')),
            ))

        # Actualizar tipo de transacción en pagos
        payments.write({
            'bancolombia_type_of_transaction': self.bancolombia_type_of_transaction
        })

        # Si está activado, también configurar en cuentas bancarias
        if self.also_set_in_bank_account:
            bank_accounts = payments.mapped('partner_bank_id').filtered(lambda b: b)
            if bank_accounts:
                bank_accounts.write({
                    'bancolombia_type_of_transaction': self.bancolombia_type_of_transaction
                })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tipo de Transacción Configurado'),
                'message': _(
                    'Se ha configurado el tipo de transacción %(type)s en %(count)d pago(s).',
                    # La selection se declara con nombre de método: en 19
                    # Field.selection guarda ese texto, no la lista.
                    type=dict(self._fields['bancolombia_type_of_transaction']._description_selection(self.env)).get(self.bancolombia_type_of_transaction),
                    count=len(payments),
                ),
                'type': 'success',
                'sticky': False,
            }
        }
