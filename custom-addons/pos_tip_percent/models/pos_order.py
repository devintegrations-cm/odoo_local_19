# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    iface_tippercent = fields.Boolean(string="POS Tip % Button")
    tip_percent1 = fields.Float(string='Tip1 %')
    tip_percent2 = fields.Float(string='Tip2 %')
    tip_percent3 = fields.Float(string='Tip3 %')
    tip_percent_base = fields.Selection(
        [
            ('without_tax', 'Total sin impuestos'),
            ('with_tax', 'Total con impuestos'),
        ],
        string='Base para el calculo de la propina',
        default='without_tax',
        required=True,
        help="Sobre que importe se aplica el porcentaje.\n"
             "- Total sin impuestos: sobre el subtotal, sin IVA. Es el comportamiento historico.\n"
             "- Total con impuestos: sobre el total que paga el cliente, IVA incluido.\n"
             "En ambos casos se descuenta la propina ya cargada, para que aplicar un porcentaje "
             "dos veces no capitalice sobre la propina anterior.\n\n"
             "IMPORTANTE: el producto de propina no deberia tener impuestos configurados. "
             "Odoo guarda la propina como precio unitario, o sea el neto, asi que si el producto "
             "lleva impuestos el cliente termina pagando mas que el importe del boton "
             "(un 10% se vuelve 11,5% efectivo con IVA del 15%).",
    )
    tip_percent_decimals = fields.Integer(
        string='Decimales de la propina',
        default=0,
        help="Cuantos decimales conservar al redondear la propina.\n\n"
             "0 redondea a la unidad, que es lo adecuado en monedas de baja denominacion "
             "(COP, CLP, CRC) y evita importes incomodos de cobrar. Con 0 decimales, en cambio, "
             "una moneda de alta denominacion puede hacer que 10% y 15% den el mismo importe.\n\n"
             "Este ajuste solo sirve para BAJAR la precision. Subirlo por encima de los decimales "
             "de la moneda no tiene efecto: el redondeo de la moneda gana igual, tanto al mostrar "
             "el importe como al guardarlo. Verificado con 4 decimales sobre una moneda de 2.",
    )

    @api.constrains('tip_percent_decimals')
    def _check_tip_percent_decimals(self):
        for config in self:
            if not 0 <= config.tip_percent_decimals <= 6:
                raise ValidationError(
                    _("Los decimales de la propina deben estar entre 0 y 6.")
                )
