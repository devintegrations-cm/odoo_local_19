# -*- coding: utf-8 -*-
import requests
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    reference_cost = fields.Float(string="Reference Cost")
    percentage_difference_cost = fields.Float(string="Percentage Difference Cost", help="Have to be between 0-1")
    @api.constrains('percentage_difference_cost')
    def _check_percentage_difference_cost(self):
        for record in self:
            if not 0 <= record.percentage_difference_cost <= 1:
                raise ValidationError("The Percentage Difference Cost must be between 0 and 1.")

    def calculate_difference_percentage(self):
        telegram_config = self.env['telegram.alerts.config'].search([], limit=1)
        if not telegram_config:
            raise ValueError("Telegram configuration not found.")

        for product in self:
            if product.standard_price:
                difference = ((product.reference_cost - product.standard_price) / product.standard_price) * 100
                message = f"The percentage difference between reference cost and standard price is {difference:.2f}%"
                telegram_config.send_alert(message)
            else:
                message = "Standard price is zero, cannot calculate difference."
                telegram_config.send_alert(message)
    
    def send_cost_differences(self, telegram_id):
        telegram_config = self.env['telegram.alerts.config'].search([('identifier', '=', telegram_id)], limit=1)
        if not telegram_config:
            raise ValueError("Telegram configuration not found.")

        # Filtrar productos con valores establecidos
        products_above_threshold = []
        products = self.search([
            #('standard_price', '!=', 0.0),
            ('reference_cost', '!=', 0.0),
            ('percentage_difference_cost', '!=', 0.0)
        ])
        
        for product in products:
            msginfo = ''
            if product.standard_price and product.reference_cost and product.percentage_difference_cost:
                difference = abs((product.reference_cost - product.standard_price) / product.standard_price) * 100
                if difference > product.percentage_difference_cost * 100:
                    msginfo = f"{product.name}: \t $ {product.standard_price:.2f} ({difference:.2f}%)"
            if product.standard_price == 0 and product.reference_cost and product.percentage_difference_cost:
                msginfo = f"{product.name} with cost: {product.standard_price}"
            if msginfo:
                products_above_threshold.append(msginfo)

        if products_above_threshold:
            message = "Productos con costo por fuera del umbral\n\n Nombre Producto  |  Costo  | (%) \n" + "\n".join(products_above_threshold)
            telegram_config.send_alert(message)
