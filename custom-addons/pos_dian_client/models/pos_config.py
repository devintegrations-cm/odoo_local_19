# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    show_dian_client_button = fields.Boolean(
        string="Validación DIAN de cliente",
        default=True,
        help=(
            "Muestra el botón 'Factura electrónica' en la pantalla de la orden "
            "para validar y asignar el cliente contra la DIAN antes de facturar."
        ),
    )
    hide_partner_button = fields.Boolean(
        string="Ocultar botón de cliente",
        default=False,
        help=(
            "Oculta el botón nativo de Cliente en la vista de orden y de pago; "
            "el cliente se gestiona solo con 'Factura electrónica' (que muestra "
            "el nombre del cliente asignado cuando está oculto). No hay forma de "
            "desasignar un cliente desde la interfaz con esta opción activa."
        ),
    )
