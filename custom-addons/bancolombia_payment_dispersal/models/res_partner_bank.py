# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _, exceptions

_logger = logging.getLogger(__name__)

class ResPartnerBank(models.Model):

    _inherit = 'res.partner.bank'
    
    @staticmethod
    def _get_bancolombia_type_of_transaction():
        return [
            ('23', _('Pre-notification Checking Account')),
            ('25', _('Cash Payment')),
            ('27', _('Deposit to Checking Account')),
            ('33', _('Pre-notify savings account')),
            ('36', _('Manager\'s Check Payment')),
            ('37', _('Deposit to Savings Account')),
            ('40', _('Secure Cash (Visa Payments)')),
            ('52', _('Electronic deposit payment')),
            ('53', _('Pre-notification of Electronic Deposit'))
        ]

    bancolombia_type_of_transaction = fields.Selection(
        selection='_get_bancolombia_type_of_transaction', string='Type of transaction')