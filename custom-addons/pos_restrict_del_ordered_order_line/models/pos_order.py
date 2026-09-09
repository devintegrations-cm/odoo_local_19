from odoo import models, fields, api


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    ordered_quantities = fields.Float(
        string="Ordered Quantities",
        default=0,
        readonly=False,
        store=True,
        help="Cantidad de este producto que ya fue enviada a cocina. No puede reducirse ni eliminarse si es mayor a 0."
    )

    @api.model
    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        fields.append('ordered_quantities')
        return fields
