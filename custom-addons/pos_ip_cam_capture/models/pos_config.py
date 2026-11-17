# -*- coding: utf-8 -*-

from odoo import models, fields, _


class PosConfig(models.Model):
    _inherit = 'pos.config'

    enable_local_ip_camera = fields.Boolean(string="Activar conexión con cámara IP", help="Habilita la conexión con la cámara IP")
    camera_url = fields.Char(string="URL de la cámara IP", help="Guarda la URL de la cámara IP")
    camera_ip = fields.Char(string="IP de la cámara", help="Guarda la IP de la cámara")
    camera_port = fields.Char(string="Puerto de la cámara IP", help="Guarda el puerto de la cámara IP")
    camera_user = fields.Char(string="Usuario de la cámara IP", help="Guarda el usuario de la cámara IP")
    camera_password = fields.Char(string="Contraseña de la cámara IP", help="Guarda la contraseña de la cámara IP")
