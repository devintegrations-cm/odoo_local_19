# -*- coding: utf-8 -*-

from odoo import fields, models


class PosConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Every related field carries the pos_ prefix: res.config.settings is one
    # shared transient, so unprefixed names collide with other modules.
    pos_enable_obligatory_ask_number_customers = fields.Boolean(
        related="pos_config_id.enable_obligatory_ask_number_customers",
        readonly=False,
        string="Preguntar número de clientes",
    )
    pos_number_customers_min = fields.Integer(
        related="pos_config_id.number_customers_min",
        readonly=False,
        string="Mínimo de clientes",
    )
    pos_number_customers_max = fields.Integer(
        related="pos_config_id.number_customers_max",
        readonly=False,
        string="Máximo de clientes",
    )
