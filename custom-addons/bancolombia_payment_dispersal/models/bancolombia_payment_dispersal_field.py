# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class BancolombiaPaymentDispersalField(models.Model):

    _name = 'bancolombia.payment_dispersal_field'
    _inherit = "account.payment_dispersal_field"
    _order = "sequence asc"
    _description = 'Configuration of the fields to be displayed in the excel file for payments in bancolombia'
