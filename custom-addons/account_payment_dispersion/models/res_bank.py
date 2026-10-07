# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _, exceptions

_logger = logging.getLogger(__name__)

class ResBank(models.Model):

    _inherit = 'res.bank'
    
    code = fields.Char(string='Code')