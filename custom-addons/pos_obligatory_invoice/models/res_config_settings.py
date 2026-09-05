# -*- coding: utf-8 -*-

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_enable_obin = fields.Boolean(related='pos_config_id.enable_obin', readonly=False)
