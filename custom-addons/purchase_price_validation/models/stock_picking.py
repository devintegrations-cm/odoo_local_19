# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        """Override to validate price variations before validating incoming receptions"""
        enable_validation = self.env['ir.config_parameter'].sudo().get_param(
            'purchase_price_validation.enable_stock_validation', 'True'
        ) == 'True'
        
        if enable_validation and self.picking_type_id.code == 'incoming':
            list_products = self.get_list_products_variation()
            if len(list_products['variation']) > 0 or len(list_products['zero']) > 0:
                message = self._generate_variation_message(list_products)
                if self.env.user.has_group('stock.group_stock_manager'):
                    message += "<br><br><p>¿Como Administrador desea confirmar la recepción de inventario con estas variaciones?</p>"
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Confirmación de recepción'),
                        'res_model': 'confirmation.variation.wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_message': message,
                            'default_stock_picking_id': self.id,
                        }
                    }
                else:
                    message += "<br><br><p>Comuniquese con el <b>Administrador</b>.</p>"
                    return {
                        'type': 'ir.actions.act_window',
                        'name': _('Advertencia recepción con variación de costos'),
                        'res_model': 'warning.variation.wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_message': message,
                        }
                    }
        return super(StockPicking, self).button_validate()

    def get_list_products_variation(self):
        """Get list of products with price variations in stock picking moves"""
        list_products = {
            'variation': [],
            'zero': []
        }
        for picking in self:
            for move in picking.move_ids:
                product = move.product_id
                if product and product.type == 'consu':
                    price_unit = move.price_unit
                    if price_unit == 0:
                        list_products['zero'].append({
                            'name': product.name,
                            'porcent_variation': product.porcent_variation
                        })
                    else:
                        cost = product.standard_price
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
        """Continue with stock picking validation after wizard approval"""
        _logger.info(f"Continuando flujo para la recepción: {self.id}")
        return super(StockPicking, self).button_validate()

    def _generate_variation_message(self, products_with_variation):
        """Generate HTML message for variation warnings"""
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
