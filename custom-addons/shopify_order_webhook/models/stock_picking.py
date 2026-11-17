from odoo import models
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _action_done(self):
        """After picking validation, create the Shopify invoice when the
        order's company has trigger == 'on_delivery'.

        ``_action_done`` is the internal hook fired once the picking
        transitions to the 'done' state — preferred over overriding
        ``button_validate`` which may also return a wizard dict.
        """
        res = super()._action_done()

        for picking in self:
            sale_order = picking.sale_id
            if not sale_order or not sale_order.is_shopify_order:
                continue
            if sale_order.company_id.shopify_invoice_trigger != 'on_delivery':
                continue
            try:
                sale_order._shopify_process_invoice()
            except Exception as e:
                _logger.error(
                    "Shopify on-delivery invoice failed for %s: %s",
                    sale_order.name, e, exc_info=True,
                )
        return res
