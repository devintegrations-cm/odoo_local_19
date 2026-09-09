from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    cash_in_out_message_enabled = fields.Boolean(
        string="Habilitar mensaje en movimiento de Efectivo",
        default=False,
        help="Pedir confirmación antes de registrar un movimiento de efectivo.",
    )
    cash_in_out_message = fields.Text(
        string="Mensaje de movimiento de Efectivo",
        help="Mensaje mostrado en el popup de confirmación de los movimientos de efectivo.",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Both related fields carry the pos_ prefix: res.config.settings is a single
    # shared transient, and an unprefixed name like `cash_in_out_message` can
    # collide with any other module that defines the same field.
    pos_cash_in_out_message_enabled = fields.Boolean(
        related="pos_config_id.cash_in_out_message_enabled",
        readonly=False,
        string="Mensaje de movimiento de Efectivo habilitado",
        help="Muestra un mensaje configurable y pide confirmación antes de "
             "registrar un movimiento de efectivo.",
    )
    pos_cash_in_out_message = fields.Text(
        related="pos_config_id.cash_in_out_message",
        readonly=False,
        string="Mensaje de movimiento de Efectivo",
        help="Texto mostrado en el popup de confirmación de los movimientos de "
             "efectivo.",
    )
