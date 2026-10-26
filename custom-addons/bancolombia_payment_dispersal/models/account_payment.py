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
                # Solo se limpia en borrador: no se toca el histórico.
                if payment.state == 'draft':
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
        Tipo de transacción tomado de la cuenta destino.

        Prioridad:
        1. Tipo configurado en la cuenta bancaria del beneficiario.
        2. Deducido del tipo de cuenta (ahorros=37, corriente=27).

        En borrador se recalcula siempre que cambia una dependencia (tercero,
        cuenta, datos de la cuenta, método), como en la v17: si la cuenta pasa
        de ahorros a corriente, el tipo no puede quedarse en 37. Un tipo
        elegido a mano se respeta mientras no cambien esas dependencias. Si la
        cuenta nueva no permite deducirlo queda vacío y la validación del lote
        ("Falta Tipo de Transacción") lo detecta, en vez de arrastrar el
        anterior o inventar uno.

        Fuera de borrador nunca se pisa un valor: es el dato con el que se
        generó (o se va a generar) el archivo. Solo se completa si está vacío.
        """
        for payment in self:
            if payment.payment_method_code != 'bancolombia_dispersion':
                # Solo se limpia en borrador. Los pagos históricos (método
                # Manual de la v17) conservan el tipo con el que se generó el
                # archivo: editar la cuenta del tercero dispara este cálculo
                # y no debe borrar ese dato.
                if payment.state == 'draft':
                    payment.bancolombia_type_of_transaction = False
                continue

            if payment.state != 'draft' and payment.bancolombia_type_of_transaction:
                continue

            # Only compute for outbound bank payments
            if payment.payment_type != 'outbound' or payment.journal_id.type != 'bank':
                continue

            transaction_type = payment.partner_bank_id._get_bancolombia_default_transaction_type()
            if transaction_type or payment.state == 'draft':
                payment.bancolombia_type_of_transaction = transaction_type
