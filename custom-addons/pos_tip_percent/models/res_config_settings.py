# -*- coding: utf-8 -*-

from odoo import models, fields, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_iface_tippercent = fields.Boolean(
        related='pos_config_id.iface_tippercent', readonly=False)
    pos_tip_percent1 = fields.Float(
        related='pos_config_id.tip_percent1', readonly=False)
    pos_tip_percent2 = fields.Float(
        related='pos_config_id.tip_percent2', readonly=False)
    pos_tip_percent3 = fields.Float(
        related='pos_config_id.tip_percent3', readonly=False)
    pos_tip_percent_base = fields.Selection(
        related='pos_config_id.tip_percent_base', readonly=False)
    pos_tip_percent_decimals = fields.Integer(
        related='pos_config_id.tip_percent_decimals', readonly=False)
