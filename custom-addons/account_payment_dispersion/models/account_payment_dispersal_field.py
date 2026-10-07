# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AccountPaymentDispersalField(models.Model):

    _name = 'account.payment_dispersal_field'
    _description = 'configuration of the fields to export the information for the dispersion files'
    _order = "sequence asc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.constrains('name')
    def _constrains_name(self):
        for rec in self:
            if self.search_count([('name', '=ilike', rec.name)]) > 1:
                raise ValidationError(
                    _("There is already a register under this name %s. Please check with your administrator", rec.name))

    name = fields.Char(string='Field name excel',
                       required=True, tracking=True, translate=True)
    active = fields.Boolean(string='Active', default=True, tracking=True)
    value = fields.Text(string='Field value', tracking=True)
    sequence = fields.Integer(string='Sequence', tracking=True)
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', default=lambda self: self.env.company.id, tracking=True)