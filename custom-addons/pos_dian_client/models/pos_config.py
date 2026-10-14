# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    show_dian_client_button = fields.Boolean(
        string="Validación cliente (DIAN)",
        default=True,
        help=(
            "Muestra el botón 'Factura electrónica' en la pantalla de la orden "
            "para validar y asignar el cliente contra la DIAN antes de facturar."
        ),
    )
