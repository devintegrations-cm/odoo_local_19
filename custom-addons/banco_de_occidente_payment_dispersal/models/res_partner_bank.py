# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class ResPartnerBank(models.Model):
    """
    Extension of res.partner.bank for Banco de Occidente-specific fields.

    Adds payment form and service type fields that can be configured per
    bank account and used as defaults for payments.
    """
    _inherit = 'res.partner.bank'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

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

    bancodeoccidente_form_of_payment = fields.Selection(
        selection='_get_bancodeoccidente_form_of_payment',
        string='Forma de Pago (Banco Occidente)',
        help='Forma de pago predeterminada para pagos Banco de Occidente con esta cuenta'
    )

    bancodeoccidente_type_of_service = fields.Selection(
        selection='_get_bancodeoccidente_type_of_service',
        string='Tipo de Servicio (Banco Occidente)',
        help='Tipo de servicio predeterminado para pagos Banco de Occidente con esta cuenta'
    )