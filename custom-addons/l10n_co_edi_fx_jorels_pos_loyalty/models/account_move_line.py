from odoo import api, models, fields

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    invoice_reward_line = fields.Boolean(string='Es premio', default=False)
    #invoice_reward_price = fields.Float(string='Precio Premio', store=True, compute='_compute_invoice_reward_price')
    # Allow NULL to avoid full-table UPDATE on install for large datasets.
    invoice_reward_price = fields.Float(string='Precio Premio')
    # adds this fields for compatibility
    reward_product_tag_target_id = fields.Float(string='Producto Premio Target Etiqueta')
    target_order_line = fields.Float(string='Linea de Orden Id')

    #@api.depends('invoice_reward_price')
    def _compute_invoice_reward_price(self):
        for inv in self:
            if inv.invoice_reward_line:
                inv.invoice_reward_price = 1*inv.price_unit
                inv.price_unit = 0.0
            else:
                inv.invoice_reward_price = 0.0
