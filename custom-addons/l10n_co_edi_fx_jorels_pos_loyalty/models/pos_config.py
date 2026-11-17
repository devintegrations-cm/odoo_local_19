# -*- coding: utf-8 -*-

from odoo import models, fields, _


class PosConfig(models.Model):
    _inherit = 'pos.config'

    enable_obligatory_invoice = fields.Boolean(string="Enable Obligatory Invoice", help="Set if you wanto to enable Obligatory invoice seleted on POS", default=False)