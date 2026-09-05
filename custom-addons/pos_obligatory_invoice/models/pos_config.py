# -*- coding: utf-8 -*-
from odoo import models, fields


class PosConfig(models.Model):
    _inherit = 'pos.config'

    # pos.config no define _load_pos_data_fields, asi que el mixin lee todos los
    # campos y este flag viaja al POS sin loader (ver models/pos_load_mixin.py).
    enable_obin = fields.Boolean(
        string="Facturacion obligatoria",
        help="Fuerza a facturar todos los pedidos de este punto de venta.",
    )
