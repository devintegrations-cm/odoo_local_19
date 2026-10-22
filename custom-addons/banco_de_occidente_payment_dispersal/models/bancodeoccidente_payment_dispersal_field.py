# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BancodeoccidentePaymentDispersalField(models.Model):

    _name = 'bancodeoccidente.payment_dispersal_field'
    _inherit = "account.payment_dispersal_field"
    _order = "sequence asc"
    _description = 'Configuration of the fields to be displayed in the excel file for payments with Banco de Occidente.'

    max_length = fields.Integer(string='Max length')
    fill_with_zeros = fields.Boolean(string='Fill with zeros')
    fill_with_spaces = fields.Boolean(string='Fill with spaces')

    @api.constrains('fill_with_zeros', 'fill_with_spaces')
    def _constrains_fill_options(self):
        for rec in self:
            if rec.fill_with_zeros and rec.fill_with_spaces:
                raise ValidationError(
                    _("You cannot fill with zeros and spaces at the same time, select only one."))
