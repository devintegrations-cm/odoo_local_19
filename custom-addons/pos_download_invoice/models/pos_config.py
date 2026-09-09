# -*- coding: utf-8 -*-

from odoo import models, fields, _


class PosConfig(models.Model):
    _inherit = 'pos.config'

    enable_download_invoice = fields.Boolean(string="Descargar factura PDF en botón del Punto de Venta", help="Si es True, permite descargar la factura, pero si es False, la desactiva", default=False)