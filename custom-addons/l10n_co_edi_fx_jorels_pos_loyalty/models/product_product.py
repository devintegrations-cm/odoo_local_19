# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class ProductProduct(models.Model):
    _inherit = 'product.product'

    reward_price = fields.Float(string='Precio Premio', default=0.0)

    def get_data_fields(self, obj):
        data_fields = {}
        for k in dir(obj):
            try:
                if not k.startswith('_'):
                    if obj[k].id:
                        data_fields[k] = obj[k]
            except:
                pass
        return data_fields
