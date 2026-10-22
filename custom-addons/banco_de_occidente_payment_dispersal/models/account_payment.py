# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    """
    Extension of account.payment for Banco de Occidente-specific fields.

    Adds payment form and service type fields required for Banco de Occidente
    dispersal files.
    """
    _inherit = 'account.payment'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    @api.model
    def _get_bancodeoccidente_form_of_payment(self):
        """
        Get Banco de Occidente payment forms.

        Returns:
            list: List of tuples (code, name)
        """
        return [
            ('payment_by_cheque', self.env._('Pago con Cheque')),
            ('credit_to_bancodeoccidente_account', self.env._('Abono a Cuenta Banco de Occidente')),
            ('credit_to_other_entities_accounts', self.env._('Abono a Cuentas de Otras Entidades')),
            ('payment_in_cash', self.env._('Pago en Efectivo'))
        ]

    @api.model
    def _get_bancodeoccidente_type_of_service(self):
        """
        Get Banco de Occidente service types.

        Returns:
            list: List of tuples (code, name)
        """
        return [
            ('notice_to_beneficiary', self.env._('1 - Aviso al Beneficiario')),
            ('stop_control', self.env._('2 - Control de Tope')),
            ('warning_and_control', self.env._('3 - Aviso y Control'))
        ]

    @api.model
    def _get_method_codes_using_bank_account(self):
        res = super()._get_method_codes_using_bank_account()
        res.append('banco_occidente_dispersion')
        return res

    @api.model
    def _get_method_codes_needing_bank_account(self):
        res = super()._get_method_codes_needing_bank_account()
        res.append('banco_occidente_dispersion')
        return res

    bancodeoccidente_form_of_payment = fields.Selection(
        selection='_get_bancodeoccidente_form_of_payment',
        string='Forma de Pago (Banco Occidente)',
        tracking=True,
        compute='_compute_bancodeoccidente_fields',
        store=True,
        readonly=False,
        help='Forma de pago para archivos de dispersión Banco de Occidente'
    )

    bancodeoccidente_type_of_service = fields.Selection(
        selection='_get_bancodeoccidente_type_of_service',
        string='Tipo de Servicio (Banco Occidente)',
        tracking=True,
        compute='_compute_bancodeoccidente_fields',
        store=True,
        readonly=False,
        help='Tipo de servicio para archivos de dispersión Banco de Occidente'
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('partner_id', 'partner_bank_id',
                 'partner_bank_id.bancodeoccidente_form_of_payment',
                 'partner_bank_id.bancodeoccidente_type_of_service',
                 'payment_type', 'journal_id.type', 'payment_method_code')
    def _compute_bancodeoccidente_fields(self):
        """
        Auto-populate Banco de Occidente fields from partner bank account.

        This provides default values but allows manual override.
        """
        for payment in self:
            if payment.payment_method_code != 'banco_occidente_dispersion':
                payment.bancodeoccidente_form_of_payment = False
                payment.bancodeoccidente_type_of_service = False
                continue

            # Only compute for outbound bank payments
            if (payment.payment_type != 'outbound' or
                payment.journal_id.type != 'bank' or
                not payment.partner_bank_id):
                continue

            # Get defaults from bank account if not already set
            if (not payment.bancodeoccidente_form_of_payment and
                payment.partner_bank_id.bancodeoccidente_form_of_payment):
                payment.bancodeoccidente_form_of_payment = (
                    payment.partner_bank_id.bancodeoccidente_form_of_payment
                )

            if (not payment.bancodeoccidente_type_of_service and
                payment.partner_bank_id.bancodeoccidente_type_of_service):
                payment.bancodeoccidente_type_of_service = (
                    payment.partner_bank_id.bancodeoccidente_type_of_service
                )
