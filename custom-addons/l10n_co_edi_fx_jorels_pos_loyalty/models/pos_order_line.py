import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    # Id de product.product del producto regalado (el que el JS toma de la línea de
    # premio de pos_loyalty). El nombre "product_line" es histórico; no se renombra
    # porque la base de producción tiene datos en esta columna.
    reward_related_product_line_id = fields.Integer(
        string="Related reward to product line id",
        help="Points to the target product id template",
        default=0.0
    )

    reward_related_order_line_id = fields.Integer(
        string="Related reward order line id",
        help="Points to the target line id",
        compute='_compute_reward_related_order_line_id',
        store=True
    )

    @api.depends('reward_related_product_line_id', 'order_id.lines.product_id')
    def _compute_reward_related_order_line_id(self):
        for line in self:
            related_line = line.order_id.lines.filtered(
                lambda l: l.product_id.id == line.reward_related_product_line_id
            )
            # [:1]: en 17 dos líneas con el mismo producto lanzaban "Expected singleton"
            # al sincronizar el pedido.
            line.reward_related_order_line_id = related_line[:1].id or 0

    @api.model
    def _load_pos_data_fields(self, config):
        # 19: los campos listados aquí son los que el JS del POS conoce y serializa al
        # sincronizar el pedido (reemplaza a _order_line_fields de 17). Solo se agrega el
        # campo que escribe el POS; reward_related_order_line_id es calculado almacenado
        # y no debe llegar desde el POS (un valor enviado en create lo protegería del
        # cálculo).
        params = super()._load_pos_data_fields(config)
        params += ['reward_related_product_line_id']
        return params
