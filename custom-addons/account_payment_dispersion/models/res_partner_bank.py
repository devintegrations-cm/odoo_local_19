# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _, exceptions

_logger = logging.getLogger(__name__)

class ResPartnerBank(models.Model):

    _inherit = 'res.partner.bank'
    
    type_of_account = fields.Selection(
        selection=[
            ('no_account', 'No Account'),
            ('current_account', 'Checking Account'),
            ('savings_account', 'Savings Account'),
            ('payroll_account', 'Payroll Account')
        ],
        string='Type of account'
    )