# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _, exceptions

_logger = logging.getLogger(__name__)


class AccountPaymentDispersalField(models.Model):

    _name = 'account.payment_dispersal'
    _description = 'It shows the dispersions that have taken place over time.'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    name = fields.Char(string='Name', required=True, tracking=True)
    active = fields.Boolean(string='Active', default=True, tracking=True)
    binary_file = fields.Binary(string='File', tracking=True)
    binary_file_name = fields.Char(string='File name', tracking=True)

    account_payment_ids = fields.Many2many(comodel_name='account.payment', relation="bancolombia_payment_dispersal_account_payment_rel",
                                           column1="bancolombia_payment_dispersal_id", column2="account_payment_id", string='Payments')
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', default=lambda self: self.env.company.id, tracking=True)

    journal_id = fields.Many2one('account.journal', string='Journal', tracking=True)