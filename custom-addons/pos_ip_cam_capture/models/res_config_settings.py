# -*- coding: utf-8 -*-

from odoo import models, fields, _


class PosConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_enable_local_ip_camera = fields.Boolean(related="pos_config_id.enable_local_ip_camera", readonly=False)
    pos_camera_url = fields.Char(related="pos_config_id.camera_url", readonly=False)
    pos_camera_ip = fields.Char(related="pos_config_id.camera_ip", readonly=False)
    pos_camera_port = fields.Char(related="pos_config_id.camera_port", readonly=False)
    pos_camera_user = fields.Char(related="pos_config_id.camera_user", readonly=False)
    pos_camera_password = fields.Char(related="pos_config_id.camera_password", readonly=False)
