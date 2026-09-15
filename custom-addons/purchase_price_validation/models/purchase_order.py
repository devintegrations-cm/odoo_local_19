# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def write(self, values):
        result = super(PurchaseOrder, self).write(values)
        enable_validation = self.env['ir.config_parameter'].sudo().get_param(
            'purchase_price_validation.enable_purchase_validation', 'True'
        ) == 'True'
        
        if enable_validation and 'order_line' in values:
            list_products = self.get_list_products_variation()
            if len(list_products['variation']) > 0 or len(list_products['zero']) > 0:
                if not self.env.user.has_group('stock.group_stock_manager'):
                    message = "¡Advertencia!\n"
                    message += "\nLos siguientes productos tienen una variación en sus costos diferente a los establecidos:\n\n"
                    for product in list_products['variation']:
                        message += f"""{product['name']}\n"""
                    for product in list_products['zero']:
                        message += f"""{product['name']}\n"""
                    message += "\n\nComuniquese con el Administrador."
                    raise UserError(message)
        return result

    def button_confirm(self):
        enable_validation = self.env['ir.config_parameter'].sudo().get_param(
            'purchase_price_validation.enable_purchase_validation', 'True'
        ) == 'True'
        
        if not enable_validation:
            return super(PurchaseOrder, self).button_confirm()
            
        list_products = self.get_list_products_variation()
        if len(list_products['variation']) > 0 or len(list_products['zero']) > 0:
            message = self._generate_variation_message(list_products)
            if self.env.user.has_group('stock.group_stock_manager'):
                message += "<br><br><p>¿Como Administrador desea confirmar la orden de compra con estas variaciones?</p>"
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Confirmación de orden'),
                    'res_model': 'confirmation.variation.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_message': message,
                        'default_purchase_order_id': self.id,
                    }
                }
            else:
                message += "<br><br><p>Comuniquese con el <b>Administrador</b>.</p>"
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Advertencia orden con variación de costos'),
                    'res_model': 'warning.variation.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_message': message,
                    }
                }
        else:
            return super(PurchaseOrder, self).button_confirm()
        
    def get_list_products_variation(self):
        list_products = {
            'variation': [],
            'zero': []
        }
        for order in self:
            for line in order.order_line:
                product = line.product_id
                if product and product.type == 'consu':
                    if line.price_unit == 0:
                        list_products['zero'].append({
                            'name': product.name,
                            'porcent_variation': product.porcent_variation
                        })
                    else:
                        cost = product.standard_price 
                        price_unit = line.price_unit
                        variation = abs(price_unit - cost) / (cost or price_unit) * 100

                        if variation > product.porcent_variation:
                            list_products['variation'].append({
                                'name': product.name,
                                'porcent_variation': "{:.2f}".format(product.porcent_variation),
                                'variation': "{:.2f}".format(variation),
                                'cost': "$ {:.2f}".format(cost),
                                'new_cost': "$ {:.2f}".format(price_unit)
                            })
                            
        return list_products     
    
    def _continue_confirmation(self):
        _logger.error(f"Continuando flujo para la orden: {self.id}")
        return super(PurchaseOrder, self).button_confirm()
    
    def _generate_variation_message(self, products_with_variation):
        message = "<div style='font-family: Arial, sans-serif;'>"
        message += "<h2 style='color: #d9534f; margin-bottom: 15px;'>¡Advertencia!</h2>"
        
        if len(products_with_variation['variation']) > 0:
            message += "<p style='margin: 10px 0;'>Los siguientes productos tienen una variación del precio unitario mayor al costo establecido:</p>"
            message += """
                <table style="width:100%; border: 1px solid #333; border-collapse: collapse; margin: 15px 0; background-color: #fff;">
                    <thead>
                        <tr style="background-color: #f5f5f5;">
                            <th style="border: 1px solid #333; padding: 8px; text-align: left; font-weight: bold;">Producto</th>
                            <th style="border: 1px solid #333; padding: 8px; text-align: center; font-weight: bold;">Variación permitida</th>
                            <th style="border: 1px solid #333; padding: 8px; text-align: center; font-weight: bold;">Variación generada</th>
                            <th style="border: 1px solid #333; padding: 8px; text-align: right; font-weight: bold;">Costo</th>
                            <th style="border: 1px solid #333; padding: 8px; text-align: right; font-weight: bold;">Costo ingresado</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for product in products_with_variation['variation']:
                message += f"""
                        <tr>
                            <td style="border: 1px solid #333; padding: 8px;">{product['name']}</td>
                            <td style="border: 1px solid #333; padding: 8px; text-align: center;">{str(product['porcent_variation'])}%</td>
                            <td style="border: 1px solid #333; padding: 8px; text-align: center; color: #d9534f; font-weight: bold;">{str(product['variation'])}%</td>
                            <td style="border: 1px solid #333; padding: 8px; text-align: right;">{str(product['cost'])}</td>
                            <td style="border: 1px solid #333; padding: 8px; text-align: right; font-weight: bold;">{str(product['new_cost'])}</td>
                        </tr>
                """
            message += """
                    </tbody>
                </table>
            """
            
        if len(products_with_variation['zero']) > 0:
            message += "<p style='margin: 10px 0;'>Los siguientes productos tienen su precio unitario igual a 0:</p>"
            message += """
                <table style="width:100%; border: 1px solid #333; border-collapse: collapse; margin: 15px 0; background-color: #fff;">
                    <thead>
                        <tr style="background-color: #f5f5f5;">
                            <th style="border: 1px solid #333; padding: 8px; text-align: left; font-weight: bold;">Producto</th>
                            <th style="border: 1px solid #333; padding: 8px; text-align: center; font-weight: bold;">Variación permitida</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for product in products_with_variation['zero']:
                message += f"""
                        <tr>
                            <td style="border: 1px solid #333; padding: 8px;">{product['name']}</td>
                            <td style="border: 1px solid #333; padding: 8px; text-align: center;">{str(product['porcent_variation'])}%</td>
                        </tr>
                """
            message += """
                    </tbody>
                </table>
            """
        
        message += "</div>"
        return message
        