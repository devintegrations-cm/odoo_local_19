# -*- coding: utf-8 -*-

from odoo import models, fields, _


class PosConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_enable_obligatory_invoice = fields.Boolean(related="pos_config_id.enable_obligatory_invoice", readonly=False)