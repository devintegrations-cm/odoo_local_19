# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    enable_obligatory_ask_number_customers = fields.Boolean(
        string="Preguntar número de clientes",
        help="Al validar el pago en la pantalla de productos se pregunta el número "
             "de clientes del pedido.",
    )
    number_customers_min = fields.Integer(
        string="Mínimo de clientes",
        default=1,
        help="Número mínimo aceptado en la pregunta de clientes.",
    )
    number_customers_max = fields.Integer(
        string="Máximo de clientes",
        default=20,
        help="Número máximo aceptado en la pregunta de clientes.",
    )

    @api.constrains('number_customers_min', 'number_customers_max')
    def _check_number_customers_range(self):
        for config in self:
            if config.number_customers_min < 1:
                raise ValidationError(_("El mínimo de clientes debe ser al menos 1."))
            if config.number_customers_max < config.number_customers_min:
                raise ValidationError(_(
                    "El máximo de clientes no puede ser menor que el mínimo."
                ))
