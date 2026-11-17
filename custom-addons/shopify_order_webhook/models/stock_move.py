from odoo import models, api


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.model_create_multi
    def create(self, vals_list):
        """Use the Shopify line description on the delivery move.

        By default ``description_picking`` is built from the product's own
        description, so the delivery would not show the text that came from
        Shopify (which lives on the sale order line ``name``). For lines
        belonging to a Shopify order we copy that line description onto the
        move so the delivery matches the sale order.

        Gated on ``shopify_order_id`` (set at order creation) rather than
        ``is_shopify_order`` (written later, after the moves already exist).
        """
        moves = super().create(vals_list)
        for move in moves:
            sale_line = move.sale_line_id
            if sale_line and sale_line.order_id.shopify_order_id and sale_line.name:
                move.description_picking = sale_line.name
        return moves
