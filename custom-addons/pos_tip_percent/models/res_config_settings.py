# -*- coding: utf-8 -*-

from odoo import models, fields, _


class PosConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_iface_tippercent = fields.Boolean(related='pos_config_id.iface_tippercent', readonly=False)
    # pos_tip_percent_ids = fields.Many2many(related='pos_config_id.tip_percent_ids', readonly=False)
    pos_tip_percent1 = fields.Float(related='pos_config_id.tip_percent1', readonly=False, store=True)
    pos_tip_percent2 = fields.Float(related='pos_config_id.tip_percent2', readonly=False, store=True)
    pos_tip_percent3 = fields.Float(related='pos_config_id.tip_percent3', readonly=False, store=True)
    # pos_fixed_tip_percentage = fields.Float(string='Fixed Tip Percentage', related='pos_config_id.fixed_tip_percentage', readonly=False, store=True)

