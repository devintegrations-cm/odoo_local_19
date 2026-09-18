# -*- coding: utf-8 -*-
from odoo import fields, models


class MaintenanceRequestCostLine(models.Model):
    _name = 'maintenance.request.cost.line'
    _description = 'Línea de costo de mantenimiento'

    request_id = fields.Many2one(
        'maintenance.request',
        string="Solicitud de mantenimiento",
        ondelete='cascade',
        required=True,
    )
    name = fields.Char(
        string="Detalle",
        required=True,
    )
    amount = fields.Monetary(
        string="Valor",
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string="Moneda",
        related='request_id.currency_id',
        store=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string="Producto",
    )
    quantity = fields.Float(
        string="Cantidad",
        default=1.0,
    )
    purchase_line_id = fields.Many2one(
        'purchase.order.line',
        string="Línea de OC",
    )
