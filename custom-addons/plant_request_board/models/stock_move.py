from odoo import api, fields, models


class StockMove(models.Model):
    """Consolidation columns on every plant order line: channel, store/customer, coffee line, size, grind, kg,
    all read from the plant fields of the product (never from its name)."""

    _inherit = "stock.move"

    plant_request = fields.Boolean(related="picking_id.plant_request", store=True, index=True)
    plant_warehouse_id = fields.Many2one(related="picking_id.plant_warehouse_id", store=True, index=True)
    plant_channel_id = fields.Many2one(related="picking_id.plant_channel_id", store=True, index=True)
    plant_channel = fields.Char(related="picking_id.plant_channel", store=True)
    plant_counterparty = fields.Char(related="picking_id.plant_counterparty", store=True, string="Tienda / cliente")
    plant_stage = fields.Selection(related="picking_id.plant_stage", store=True)
    plant_kind_id = fields.Many2one("plant.kind", string="Tipo", compute="_compute_plant_line", store=True, index=True, ondelete="restrict")
    plant_kind_code = fields.Selection(related="plant_kind_id.code", string="Cómo se cuenta")
    plant_coffee_line = fields.Char(string="Línea de café", compute="_compute_plant_line", store=True)
    plant_size = fields.Char(string="Presentación", compute="_compute_plant_line", store=True)
    plant_grind = fields.Char(string="Molienda", compute="_compute_plant_line", store=True)
    plant_kg = fields.Float(string="Kg de café", compute="_compute_plant_line", store=True, digits=(12, 3), help="Bolsas × gramaje, o los gramos pedidos de café para preparar.")
    plant_bags = fields.Float(string="Bolsas / unidades", compute="_compute_plant_line", store=True, digits=(12, 0))

    @api.model
    def _plant_bag_grams(self, product, rules=None):
        """Grams of coffee per unit of the product: its plant field (of its master), else its weight."""
        grams = product.product_tmpl_id._plant_values(rules["parser"] if rules else None)["grams"]
        return grams or (product.weight * 1000.0 if product.weight else 0.0)

    @api.depends("product_id", "product_uom_qty", "product_uom", "picking_id.plant_request")
    def _compute_plant_line(self):
        Picking = self.env["stock.picking"]
        rules = Picking._plant_line_rules()
        for mv in self:
            if not mv.picking_id.plant_request or not mv.product_id:
                mv.plant_kind_id = False
                mv.plant_coffee_line = mv.plant_size = mv.plant_grind = False
                mv.plant_kg = mv.plant_bags = 0.0
                continue
            desc = Picking._plant_describe(mv.product_id, rules)
            mv.plant_kind_id = rules["kinds"].get(desc["kind"])
            mv.plant_coffee_line = (desc["line"] or False) if desc["kind"] != "supply" else False
            mv.plant_size = desc["size"] or False
            mv.plant_grind = desc["grind"] or False
            if desc["kind"] == "prepare":
                mv.plant_kg = Picking._plant_grams(mv) / 1000.0
                mv.plant_bags = 0.0
            elif desc["kind"] in ("packed", "ready"):
                mv.plant_kg = mv.product_uom_qty * self._plant_bag_grams(mv.product_id, rules) / 1000.0 if desc["kind"] == "packed" else 0.0
                mv.plant_bags = mv.product_uom_qty
            else:
                mv.plant_kg = 0.0
                mv.plant_bags = mv.product_uom_qty

    # --- the ticks of the request follow its lines (created, changed, removed) ---------------------------
    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves.picking_id.filtered("plant_request")._plant_sync_checks()
        return moves

    def write(self, vals):
        relevant = bool(vals.keys() & {"product_id", "product_uom_qty", "product_uom", "picking_id"}) or vals.get("state") == "cancel"
        pickings = self.picking_id if relevant else self.env["stock.picking"]
        res = super().write(vals)
        if relevant:
            (pickings | self.picking_id).filtered("plant_request")._plant_sync_checks()
        return res

    def unlink(self):
        pickings = self.picking_id.filtered("plant_request")
        res = super().unlink()
        pickings.exists()._plant_sync_checks()
        return res

    @api.model
    def _plant_reclassify_open(self, templates=None):
        """Read the open plant lines again (of the given products, or all) with the current plant fields, so a
        change in a product or in the configuration is seen at once; delivered and cancelled lines keep what they
        were."""
        domain = [("plant_request", "=", True), ("state", "not in", ("done", "cancel"))]
        if templates is not None:
            domain.append(("product_id.product_tmpl_id", "in", templates.ids))
        moves = self.sudo().search(domain)
        names = [f.name for f in self._fields.values() if f.compute == "_compute_plant_line"]
        for name in names:
            self.env.add_to_compute(self._fields[name], moves)
        moves.modified(names)   # what depends on them (the code, the card, the totals) is read again too
        moves.picking_id._plant_sync_checks()   # a product classified again may change the line of its tick
