# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    """
    Extension of account.payment for Bancolombia-specific fields.

    Adds transaction type field that determines how the payment will be
    processed by Bancolombia.
    """
    _inherit = 'account.payment'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    @api.model
    def _get_bancolombia_type_of_transaction(self):
        """
        Get Bancolombia transaction types.

        Returns:
            list: List of tuples (code, name)
        """
        return [
            ('23', self.env._('23 - Pre-notificación Cuenta Corriente')),
            ('25', self.env._('25 - Pago en Efectivo')),
            ('27', self.env._('27 - Depósito a Cuenta Corriente')),
            ('33', self.env._('33 - Pre-notificación Cuenta de Ahorros')),
            ('36', self.env._('36 - Pago con Cheque de Gerencia')),
            ('37', self.env._('37 - Depósito a Cuenta de Ahorros')),
            ('40', self.env._('40 - Efectivo Seguro (Pagos Visa)')),
            ('52', self.env._('52 - Pago Depósito Electrónico')),
            ('53', self.env._('53 - Pre-notificación Depósito Electrónico'))
        ]

    @api.model
    def _get_method_codes_using_bank_account(self):
        res = super()._get_method_codes_using_bank_account()
        res.append('bancolombia_dispersion')
        return res

    @api.model
    def _get_method_codes_needing_bank_account(self):
        res = super()._get_method_codes_needing_bank_account()
        res.append('bancolombia_dispersion')
        return res

    bancolombia_payment_type = fields.Selection(
        selection=[
            ('220', 'Proveedores (220)'),
            ('225', 'Nómina (225)'),
        ],
        string='Tipo de Dispersión (Bancolombia)',
        compute='_compute_bancolombia_payment_type',
        store=True,
        readonly=False,
        tracking=True,
        help='Tipo de archivo de dispersión Bancolombia. '
             'En pagos a proveedores se propone 220; para nómina use 225.'
    )

    bancolombia_type_of_transaction = fields.Selection(
        selection='_get_bancolombia_type_of_transaction',
        string='Tipo de Transacción Bancolombia',
        tracking=True,
        compute='_compute_bancolombia_type_of_transaction',
        store=True,
        readonly=False,
        help='Tipo de transacción para archivos de dispersión Bancolombia'
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('payment_method_code', 'partner_type')
    def _compute_bancolombia_payment_type(self):
        for payment in self:
            if payment.payment_method_code != 'bancolombia_dispersion':
                payment.bancolombia_payment_type = False
                continue
            if payment.bancolombia_payment_type:
                continue
            if payment._is_payroll_dispersion_context():
                payment.bancolombia_payment_type = '225'
            else:
                payment.bancolombia_payment_type = (
                    '220' if payment.partner_type == 'supplier' else '225'
                )

    def _get_dispersion_batch_grouping_key(self):
        self.ensure_one()
        if self.payment_method_code == 'bancolombia_dispersion':
            return self.bancolombia_payment_type or False
        return super()._get_dispersion_batch_grouping_key()

    @api.depends('partner_id', 'partner_bank_id', 'partner_bank_id.bancolombia_type_of_transaction',
                 'partner_bank_id.co_account_type', 'payment_type', 'journal_id', 'journal_id.type',
                 'payment_method_code')
    def _compute_bancolombia_type_of_transaction(self):
        """
        Auto-populate transaction type from partner bank account.

        Priority order:
        1. Bank account's configured transaction type
        2. Infer from account type (savings=37, current=27)
        3. Default to 37 (most common)

        This provides a smart default but allows manual override.
        """
        for payment in self:
            if payment.payment_method_code != 'bancolombia_dispersion':
                payment.bancolombia_type_of_transaction = False
                continue

            # Skip if already has a value (manual override)
            if payment.bancolombia_type_of_transaction:
                continue

            # Only compute for outbound bank payments
            if payment.payment_type != 'outbound' or payment.journal_id.type != 'bank':
                continue

            # Priority 1: Get from bank account configuration
            if (payment.partner_bank_id and
                payment.partner_bank_id.bancolombia_type_of_transaction):
                payment.bancolombia_type_of_transaction = (
                    payment.partner_bank_id.bancolombia_type_of_transaction
                )
                continue

            # Priority 2: Infer from account type
            if payment.partner_bank_id and payment.partner_bank_id.co_account_type:
                if payment.partner_bank_id.co_account_type == 'savings_account':
                    payment.bancolombia_type_of_transaction = '37'  # Depósito a Cuenta de Ahorros
                elif payment.partner_bank_id.co_account_type == 'current_account':
                    payment.bancolombia_type_of_transaction = '27'  # Depósito a Cuenta Corriente
                continue

            # Priority 3: Default to most common (Depósito a Cuenta de Ahorros)
            if payment.partner_bank_id:
                payment.bancolombia_type_of_transaction = '37'
