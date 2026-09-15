from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_purchase_price_validation = fields.Boolean(
        string='Validar variación de precios en Órdenes de Compra',
        config_parameter='purchase_price_validation.enable_purchase_validation',
        default=True,
        help='Activa la validación de variación de precios al confirmar órdenes de compra'
    )

    enable_stock_price_validation = fields.Boolean(
        string='Validar variación de precios en Recepciones de Inventario',
        config_parameter='purchase_price_validation.enable_stock_validation',
        default=True,
        help='Activa la validación de variación de precios al validar recepciones de inventario'
    )
