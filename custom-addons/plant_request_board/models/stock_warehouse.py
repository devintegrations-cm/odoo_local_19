from odoo import api, fields, models


class StockWarehouse(models.Model):
    """Which warehouses are plants (their outgoing transfers are requests) and which ones are stores (columns of
    PEDIDOS TIENDAS). Both are records, not codes in a setting, so a new plant or store needs no deployment."""

    _inherit = "stock.warehouse"

    plant_is_plant = fields.Boolean(string="Almacén de planta", help="Toda transferencia o entrega que sale de este almacén es una solicitud a la planta.")
    plant_is_store = fields.Boolean(string="Es tienda", help="Columna de PEDIDOS TIENDAS en la hoja de la planta. Se marca solo con la primera solicitud del almacén; desmárcalo para ocultar la tienda.")

    @api.model_create_multi
    def create(self, vals_list):
        warehouses = super().create(vals_list)
        plants = warehouses.filtered("plant_is_plant")
        if plants:
            self.env["stock.picking"]._plant_recompute_for_warehouses(plants)
        return warehouses

    def write(self, vals):
        changed = self.filtered(lambda w: w.plant_is_plant != bool(vals["plant_is_plant"])) if "plant_is_plant" in vals else self.browse()
        res = super().write(vals)
        if changed:
            # a warehouse that becomes (or stops being) a plant: every transfer that leaves it is classified again
            self.env["stock.picking"]._plant_recompute_for_warehouses(changed)
        return res
