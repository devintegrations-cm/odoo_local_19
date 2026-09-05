# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    ask_for_approval_number = fields.Boolean(
        string="Ask for approval number",
        help="Set if you want ask in pos the approval number",
    )

    @api.model
    def _load_pos_data_fields(self, config):
        # Odoo 19: la carga al POS se declara en el modelo dueno del campo.
        # `pos.session._loader_params_pos_payment_method` ya no existe.
        # Patron del core: addons/pos_hr/models/product_product.py
        result = super()._load_pos_data_fields(config)
        result.append('ask_for_approval_number')
        return result
