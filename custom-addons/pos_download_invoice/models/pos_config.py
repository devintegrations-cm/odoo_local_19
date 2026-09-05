# -*- coding: utf-8 -*-

from odoo import models, fields, _


class PosConfig(models.Model):
    _inherit = 'pos.config'

    enable_download_invoice = fields.Boolean(string="Download PDF invoice in POS Button", help="If True enable download invoice, but False disable it", default=False)