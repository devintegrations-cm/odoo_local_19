from odoo import _, api, fields, models


class PlantProductionPlan(models.TransientModel):
    """The right-hand side of the plant's sheet: per product (every equivalent reference added up in its master)
    and plant, ordered − stock at that plant = to produce, and kg to roast grouped by coffee line. Rows are
    recomputed from the open orders every time the plan is opened.

    A negative stock in Odoo (production or packing not registered yet) never adds to what has to be made: the
    stock is read as zero and the real figure is shown as a warning on the row."""

    _name = "plant.production.plan"
    _description = "Plan de producción de la planta"
    _order = "plant_coffee_line, plant_kind_id, product_id, plant_warehouse_id"

    product_id = fields.Many2one("product.product", string="Producto", readonly=True)
    product_tmpl_id = fields.Many2one("product.template", string="Referencia maestra", readonly=True)
    variant_count = fields.Integer(string="Referencias", readonly=True, help="Cuántas referencias equivalentes suman en esta fila (la maestra y sus variantes).")
    plant_warehouse_id = fields.Many2one("stock.warehouse", string="Planta", readonly=True)
    plant_kind_id = fields.Many2one("plant.kind", string="Tipo", readonly=True)
    plant_kind_code = fields.Selection(related="plant_kind_id.code")
    plant_coffee_line = fields.Char(string="Línea de café", readonly=True)
    plant_size = fields.Char(string="Presentación", readonly=True)
    plant_grind = fields.Char(string="Molienda", readonly=True)
    ordered = fields.Float(string="Bolsas pedidas", readonly=True, digits=(12, 0), help="Bolsas o unidades en los pedidos abiertos. El café para preparar va solo en kg.")
    orders = fields.Integer(string="Pedidos", readonly=True)
    counterparties = fields.Char(string="Para quién", readonly=True)
    on_hand = fields.Float(string="Bolsas en planta", readonly=True, digits=(12, 0), help="Existencias en la planta según Odoo; un inventario negativo se toma como cero.")
    on_hand_raw = fields.Float(string="Inventario en Odoo", readonly=True, digits=(12, 0), help="La cifra tal como está en Odoo, con signo.")
    to_produce = fields.Float(string="Bolsas por fabricar", readonly=True, digits=(12, 0), help="Pedidas menos en planta (nunca menos que cero), nunca negativo.")
    kg_ordered = fields.Float(string="Kg pedidos", readonly=True, digits=(12, 2), help="Bolsas × gramaje, o los kg de café para preparar.")
    kg_on_hand = fields.Float(string="Kg en planta", readonly=True, digits=(12, 2))
    kg_on_hand_raw = fields.Float(string="Kg en Odoo", readonly=True, digits=(12, 2), help="Los kg en planta tal como están en Odoo, con signo.")
    kg_to_roast = fields.Float(string="Kg a tostar", readonly=True, digits=(12, 2), help="Kg pedidos que no están en planta: bolsas por fabricar × gramaje, o kg de café para preparar faltantes. El inventario negativo nunca suma.")
    negative_stock = fields.Boolean(string="Inventario negativo", readonly=True)
    stock_note = fields.Char(string="Aviso", readonly=True)
    channels = fields.Char(string="Canales", readonly=True)

    @api.model
    def _open_lines_domain(self, channels=None, plant_id=None):
        dom = [("plant_request", "=", True), ("plant_stage", "in", ("new", "preparing")), ("state", "not in", ("done", "cancel"))]   # prepared (ready) and delivered requests are out
        if channels:
            dom.append(("plant_channel", "in", channels))
        if plant_id:
            dom.append(("plant_warehouse_id", "=", plant_id))
        return dom

    @api.model
    def _compute_rows(self, channels=None, plant_id=None):
        """The rows of the plan as values, from the open orders: one per master product and plant, compared with
        the stock of that plant (every equivalent reference included, negative stock read as zero)."""
        Move = self.env["stock.move"]
        rules = self.env["stock.picking"]._plant_line_rules()
        groups = {}
        for mv in Move.search(self._open_lines_domain(channels, plant_id)):
            master = mv.product_id.product_tmpl_id._plant_values(rules["parser"])["master"]
            g = groups.setdefault((master.id, mv.plant_warehouse_id.id), {"mv": mv, "master": master, "qty": 0.0, "kg": 0.0, "picks": set(), "who": set(), "channels": set()})
            g["qty"] += mv.product_uom_qty
            g["kg"] += mv.plant_kg
            g["picks"].add(mv.picking_id.id)
            g["who"].add(mv.plant_counterparty or "")
            g["channels"].add(mv.plant_channel_id.name or "")
        family = {}
        for g in groups.values():
            family[g["master"].id] = (g["master"] | g["master"].plant_variant_ids).with_context(active_test=False).product_variant_ids
        stock = {}
        for plant in self.env["stock.warehouse"].browse({wid for _tid, wid in groups}):
            stock[plant.id] = self.env["plant.sheet"]._stock_by_product([p for products in family.values() for p in products], plant.lot_stock_id)
        rows = []
        for (tid, wid), g in groups.items():
            mv = g["mv"]
            product = mv.product_id
            at_plant = stock.get(wid, {})
            on_hand_raw = sum(p.uom_id._compute_quantity(at_plant.get(p.id, 0.0), mv.product_uom) if p.uom_id != mv.product_uom else at_plant.get(p.id, 0.0) for p in family[tid])
            on_hand = max(on_hand_raw, 0.0)
            if mv.plant_kind_code == "prepare":
                # bulk coffee: everything in kg (the order line is in grams or kg)
                factor = 1000.0 if mv.product_uom.name.lower().startswith("g") else 1.0
                kg_on_hand_raw = on_hand_raw / factor
                kg_on_hand = max(kg_on_hand_raw, 0.0)
                ordered = on_hand_bags = on_hand_bags_raw = to_produce = 0.0
                kg_to_roast = max(g["kg"] - kg_on_hand, 0.0)
            else:
                grams = Move._plant_bag_grams(product, rules) if mv.plant_kind_code == "packed" else 0.0
                ordered, on_hand_bags, on_hand_bags_raw = g["qty"], on_hand, on_hand_raw
                to_produce = max(ordered - on_hand_bags, 0.0)
                kg_on_hand = on_hand_bags * grams / 1000.0
                kg_on_hand_raw = on_hand_bags_raw * grams / 1000.0
                kg_to_roast = to_produce * grams / 1000.0
            negative = on_hand_raw < -1e-9
            rows.append({
                "product_id": (g["master"].product_variant_id if g["master"] != product.product_tmpl_id else product).id, "product_tmpl_id": tid, "variant_count": len(family[tid]),
                "plant_warehouse_id": wid, "plant_kind_id": mv.plant_kind_id.id, "plant_coffee_line": mv.plant_coffee_line or "—", "plant_size": mv.plant_size, "plant_grind": mv.plant_grind,
                "ordered": ordered, "orders": len(g["picks"]), "counterparties": ", ".join(sorted(w for w in g["who"] if w))[:200],
                "on_hand": on_hand_bags, "on_hand_raw": on_hand_bags_raw, "to_produce": to_produce,
                "kg_ordered": g["kg"], "kg_on_hand": kg_on_hand, "kg_on_hand_raw": kg_on_hand_raw, "kg_to_roast": kg_to_roast,
                "negative_stock": negative,
                "stock_note": (_("Inventario negativo en Odoo (%s): falta registrar producción/empaque") % (("%.2f kg" % kg_on_hand_raw) if mv.plant_kind_code == "prepare" else ("%g" % on_hand_bags_raw))) if negative else False,
                "channels": ", ".join(sorted(c for c in g["channels"] if c)),
            })
        return rows

    @api.model
    def action_open(self, channels=None, plant_id=None):
        """Rebuild the plan for the current user from the open orders and open it grouped by coffee line."""
        # the rows belong to the inventory administrator (ACL); the inventory user still gets their own copy, computed here
        self.sudo().search([("create_uid", "=", self.env.uid)]).unlink()
        self.sudo().create(self._compute_rows(channels, plant_id))
        action = self.env["ir.actions.actions"]._for_xml_id("plant_request_board.action_plant_production_plan")
        action["domain"] = [("create_uid", "=", self.env.uid)]
        return action

    @api.model
    def _kg_to_roast(self, channels=None, plant_id=None):
        return sum(r["kg_to_roast"] for r in self._compute_rows(channels, plant_id))

    @api.model
    def _comparison_text(self):
        """The plan's total next to the TOTAL NETO X TOSTAR of each tab of the sheet, for the same open orders,
        and why they differ by design (shown with the "Comparar con la hoja" button of the plan)."""
        Sheet = self.env["plant.sheet"]
        tabs = [(title, Sheet.get_data(sheet=code, scope="open")["totals"]["kg"]) for code, title in Sheet.get_tabs()]
        lines = [_("Plan de tostión: %s kg.") % ("%.3f" % self._kg_to_roast()), _("TOTAL NETO X TOSTAR de la hoja para los mismos pedidos abiertos:")]
        lines += ["  · %s: %s kg" % (title, "%.3f" % kg) for title, kg in tabs]
        lines.append(_("Difieren por diseño: el plan junta todos los canales y descuenta el inventario de la planta en todos ellos, por referencia maestra; "
                       "la hoja descuenta inventario solo en PEDIDOS TIENDAS (OTROS y ATTENZA se tuestan completos), reúne en una fila el inventario de todas las "
                       "referencias de la fila y explota los kits. En ambos el inventario negativo cuenta como cero."))
        return "\n".join(lines)

    def action_compare_with_sheet(self):
        """Header button of the plan's list (display="always"). Not @api.model: on Odoo 19 the web client sends
        the selected ids (an empty list when nothing is selected) and call_kw only drops them for a method that
        is not @api.model, so the decorator turned the click into "takes 1 positional argument but 2 were given".
        The comparison does not depend on the selected rows."""
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {"type": "info", "title": _("Plan de tostión y hoja de pedidos"), "message": self._comparison_text(), "sticky": True}}
