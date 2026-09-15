# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ConfirmationVariationWizard(models.TransientModel):
    _name = 'confirmation.variation.wizard'
    _description = 'Wizard de confirmación de proceso de variación de costo'

    message = fields.Html(string="Mensaje", readonly=True, sanitize=False)
    purchase_order_id = fields.Many2one('purchase.order', string="Orden de Compra", readonly=True)
    stock_picking_id = fields.Many2one('stock.picking', string="Recepción de Inventario", readonly=True)

    def action_confirm(self):
        if self.purchase_order_id:
            return self.purchase_order_id._continue_confirmation()
        elif self.stock_picking_id:
            return self.stock_picking_id._continue_confirmation()

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
