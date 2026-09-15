# -*- coding: utf-8 -*-

from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    porcent_variation = fields.Float(string='Variación de Costo', default=10.0) 