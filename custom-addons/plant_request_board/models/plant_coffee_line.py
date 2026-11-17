from odoo import api, fields, models

# the alert of a request or a line: enough green coffee, below the minimum, missing
GREEN_STATES = [("green", "Alcanza"), ("yellow", "Por debajo del mínimo"), ("red", "Falta")]


class PlantCoffeeLine(models.Model):
    """A coffee line of the plant (Paz, Libre, Punk, Decaf, B. Rojo, Impacto…): the first level of the sheet, with
    the colour the plant paints its rows with, the roasting shrinkage of the line and the green coffee that backs
    it. Lines are records: a new one is created by the product classifier the first time a product names it, or
    by hand, never in code."""

    _name = "plant.coffee.line"
    _description = "Línea de café de la planta"
    _order = "sequence, id"

    name = fields.Char(string="Línea", required=True)
    sequence = fields.Integer(default=10, help="Orden de las líneas en la hoja y en el plan de tostión.")
    color = fields.Char(string="Color", default="#FFFFFF", help="Color de fondo de las filas de la línea en la hoja, en hexadecimal (#FFE599).")
    net_color = fields.Char(string="Color total neto", help="Color de la celda TOTAL NETO X TOSTAR de la línea, si es distinto al de la fila.")
    active = fields.Boolean(default=True)
    product_count = fields.Integer(string="Productos", compute="_compute_product_count")
    shrinkage = fields.Float(string="Merma de tostión (%)", digits=(5, 2), help="Pérdida de peso al tostar esta línea: kg verde = kg tostado ÷ (1 − merma). Vacío o cero usa la merma por defecto de Ajustes › Planta.")
    green_minimum_kg = fields.Float(string="Mínimo de café verde (kg)", digits=(12, 2), help="Por debajo de estos kg de café verde la alerta pasa a amarillo. Vacío o cero usa el mínimo por defecto de Ajustes › Planta.")
    green_product_ids = fields.Many2many("product.product", string="Café verde de la línea", compute="_compute_green", help="Productos de tipo «Café verde» de esta línea y, con listas de materiales, los componentes verdes del café tostado de la línea.")
    green_stock_kg = fields.Float(string="Café verde en planta (kg)", compute="_compute_green", digits=(12, 2), help="Existencias de café verde de la línea en las plantas; un inventario negativo se muestra como cero.")
    green_stock_raw_kg = fields.Float(string="Café verde en Odoo (kg)", compute="_compute_green", digits=(12, 2))

    _name_uniq = models.Constraint("unique(name)", "Ya existe una línea de café con ese nombre.")

    def _compute_product_count(self):
        counts = {line.id: count for line, count in self.env["product.template"]._read_group([("plant_coffee_line_id", "in", self.ids)], ["plant_coffee_line_id"], ["__count"])}
        for line in self:
            line.product_count = counts.get(line.id, 0)

    def _compute_green(self):
        locations = self.env["stock.picking"]._plant_warehouses().lot_stock_id
        greens = self._plant_green_products()
        stock = self.env["plant.sheet"]._stock_by_product([p for products in greens.values() for p in products], locations)
        for line in self:
            products = greens.get(line.id, self.env["product.product"])
            raw = sum(self._plant_kg_of(p, stock.get(p.id, 0.0)) for p in products)
            line.green_product_ids = products
            line.green_stock_raw_kg = raw
            line.green_stock_kg = max(raw, 0.0)

    # --- shrinkage and minimum: the line's own value, else the defaults of the settings ------------------
    def _plant_shrinkage(self):
        self.ensure_one()
        value = self.shrinkage or self.env["res.config.settings"]._plant_get_float("plant_default_shrinkage")
        return min(max(value, 0.0), 99.0) / 100.0

    def _plant_green_minimum(self):
        self.ensure_one()
        return self.green_minimum_kg or self.env["res.config.settings"]._plant_get_float("plant_green_minimum_kg")

    @api.model
    def _plant_green_kg(self, roasted_kg, shrinkage):
        """kg of green coffee needed to roast roasted_kg with the given shrinkage (0–0.99)."""
        return roasted_kg / (1.0 - shrinkage) if roasted_kg > 0 else 0.0

    # --- the green coffee behind each line ------------------------------------------------------------
    @api.model
    def _plant_kg_of(self, product, qty):
        """qty of the product (in its unit) as kg: weight units converted, pieces × net grams."""
        Row = self.env["plant.sheet.row"]
        if Row._is_weight(product.uom_id):
            return product.uom_id._compute_quantity(qty, Row._plant_gram(), round=False) / 1000.0
        grams = product.product_tmpl_id.plant_net_grams
        return qty * grams / 1000.0 if grams else qty

    def _plant_green_products(self):
        """{line id: green products}: the products of kind «Café verde» of the line and, when mrp is installed,
        the green components of the bills of materials of the line's roasted coffee (bulk or bags)."""
        Template = self.env["product.template"]
        out = {}
        greens = Template.search([("plant_kind_id.code", "=", "green"), ("plant_coffee_line_id", "in", self.ids)])
        for tmpl in greens:
            out[tmpl.plant_coffee_line_id.id] = out.get(tmpl.plant_coffee_line_id.id, self.env["product.product"]) | tmpl.product_variant_ids
        if "mrp.bom" in self.env:
            roasted = Template.search([("plant_kind_id.code", "in", ("prepare", "packed")), ("plant_coffee_line_id", "in", self.ids)])
            boms = self.env["mrp.bom"].sudo().search([("product_tmpl_id", "in", roasted.ids)])
            for bom in boms:
                line_id = bom.product_tmpl_id.plant_coffee_line_id.id
                for comp in bom.bom_line_ids.product_id:
                    kind = comp.product_tmpl_id._plant_values()["kind"]
                    if kind == "green":
                        out[line_id] = out.get(line_id, self.env["product.product"]) | comp
                    elif kind == "prepare" and comp.product_tmpl_id.plant_coffee_line_id.id == line_id:   # a bag made of bulk roasted coffee: the bulk coffee's own BoM holds the green
                        for inner in self.env["mrp.bom"].sudo().search([("product_tmpl_id", "=", comp.product_tmpl_id.id)]).bom_line_ids.product_id:
                            if inner.product_tmpl_id._plant_values()["kind"] == "green":
                                out[line_id] = out.get(line_id, self.env["product.product"]) | inner
        for line in self:
            out.setdefault(line.id, self.env["product.product"])
        return out

    # --- the cumulative allocation: pending requests in date order, roasted stock first, then green -------
    @api.model
    def _plant_green_allocation(self, plant_id=None, pickings=None):
        """For the pending requests of the plant(s), in order of request date: each one takes the roasted coffee
        of its lines that is in stock, what is left has to be roasted, and the green coffee it needs comes out
        of the green stock of the line. Returns per line the totals and per request the status of every line:
        green (enough), yellow (below the line's minimum after this order), red (missing green coffee)."""
        Picking = self.env["stock.picking"]
        plants = Picking._plant_warehouses()
        if plant_id:
            plants = plants.filtered(lambda w: w.id == plant_id)
        locations = plants.lot_stock_id
        domain = [("plant_request", "=", True), ("plant_stage", "in", ("new", "preparing")), ("state", "not in", ("done", "cancel")), ("plant_warehouse_id", "in", plants.ids)]
        if pickings is not None:
            domain.append(("id", "in", pickings.ids))
        pending = Picking.search(domain, order="create_date, id")
        rules = Picking._plant_line_rules()
        Template = self.env["product.template"]
        # kg of coffee each request needs per line
        needs = {}
        line_ids = set()
        for pick in pending:
            per_line = {}
            for mv in pick.move_ids.filtered(lambda m: m.state != "cancel"):
                vals = mv.product_id.product_tmpl_id._plant_values(rules["parser"])
                if vals["kind"] in ("prepare", "packed") and mv.plant_kg:
                    key = vals["line"].id if vals["line"] else 0
                    per_line[key] = per_line.get(key, 0.0) + mv.plant_kg
                    line_ids.add(key)
            needs[pick.id] = per_line
        lines = self.browse([i for i in line_ids if i])
        greens = lines._plant_green_products()
        roasted = {line.id: Template.search([("plant_kind_id.code", "in", ("prepare", "packed")), ("plant_coffee_line_id", "=", line.id)]).product_variant_ids for line in lines}
        stock = self.env["plant.sheet"]._stock_by_product([p for ps in list(greens.values()) + list(roasted.values()) for p in ps], locations)
        state = {}
        for key in line_ids:
            line = lines.filtered(lambda l: l.id == key)
            roasted_raw = sum(self._plant_kg_of(p, stock.get(p.id, 0.0)) for p in roasted.get(key, []))
            green_raw = sum(self._plant_kg_of(p, stock.get(p.id, 0.0)) for p in greens.get(key, []))
            state[key] = {
                "line_id": key, "line": line.name if line else "—", "color": (line.color if line else "") or "#FFFFFF",
                "shrinkage": line._plant_shrinkage() if line else self._plant_default_shrinkage(), "minimum": line._plant_green_minimum() if line else self.env["res.config.settings"]._plant_get_float("plant_green_minimum_kg"),
                "roasted_raw": roasted_raw, "roasted_left": max(roasted_raw, 0.0), "green_raw": green_raw, "green_left": max(green_raw, 0.0),
                "need_kg": 0.0, "to_roast_kg": 0.0, "green_needed_kg": 0.0, "negative": roasted_raw < -1e-6 or green_raw < -1e-6,
            }
        requests = []
        for pick in pending:
            alerts = []
            for key, need in sorted(needs[pick.id].items(), key=lambda item: -item[1]):
                st = state[key]
                from_roasted = min(need, st["roasted_left"])
                st["roasted_left"] -= from_roasted
                to_roast = need - from_roasted
                green_needed = self._plant_green_kg(to_roast, st["shrinkage"])
                st["green_left"] -= green_needed
                st["need_kg"] += need
                st["to_roast_kg"] += to_roast
                st["green_needed_kg"] += green_needed
                remaining = st["green_left"]
                if remaining < -1e-6 and green_needed > 1e-6:
                    status, message = "red", "Para esta solicitud te faltan %.1f kg de café verde %s" % (min(green_needed, -remaining), st["line"])
                elif green_needed <= 1e-6:
                    status, message = "green", "Sale del café tostado en planta: no gasta café verde %s" % st["line"]
                elif remaining < st["minimum"] - 1e-6:
                    status, message = "yellow", "Te quedan solo %.1f kg de café verde %s después de esta orden" % (remaining, st["line"])
                else:
                    status, message = "green", "Te quedan %.1f kg de café verde %s después de esta orden" % (remaining, st["line"])
                alerts.append({"line_id": key, "line": st["line"], "color": st["color"], "need_kg": need, "from_roasted_kg": from_roasted, "to_roast_kg": to_roast,
                               "green_needed_kg": green_needed, "remaining_kg": remaining, "status": status, "message": message})
            if not alerts:
                continue   # no coffee to roast in this request: nothing to say about green coffee
            requests.append({"picking_id": pick.id, "name": pick.name, "counterparty": pick.plant_counterparty or "", "date": fields.Datetime.context_timestamp(self, pick.create_date).strftime("%Y-%m-%d %H:%M") if pick.create_date else "",
                             "stage": pick.plant_stage, "alerts": alerts, "status": "red" if any(a["status"] == "red" for a in alerts) else "yellow" if any(a["status"] == "yellow" for a in alerts) else "green"})
        summary = []
        for key, st in sorted(state.items(), key=lambda item: (lines.filtered(lambda l: l.id == item[0]).sequence if item[0] else 9999, item[0])):
            remaining = st["green_left"]
            summary.append({
                "line_id": key, "line": st["line"], "color": st["color"], "shrinkage_pct": round(st["shrinkage"] * 100, 2), "minimum_kg": st["minimum"],
                "need_kg": st["need_kg"], "roasted_stock_kg": max(st["roasted_raw"], 0.0), "roasted_raw_kg": st["roasted_raw"], "to_roast_kg": st["to_roast_kg"],
                "green_needed_kg": st["green_needed_kg"], "green_stock_kg": max(st["green_raw"], 0.0), "green_raw_kg": st["green_raw"], "remaining_kg": remaining,
                "negative": st["negative"],
                # a line with nothing to roast has no alert; a line that roasts is red when green coffee is missing, yellow when it ends below its minimum
                "status": "green" if st["to_roast_kg"] <= 1e-6 else "red" if remaining < -1e-6 else "yellow" if remaining < st["minimum"] - 1e-6 else "green",
            })
        return {"lines": summary, "requests": requests}

    @api.model
    def _plant_default_shrinkage(self):
        return min(max(self.env["res.config.settings"]._plant_get_float("plant_default_shrinkage"), 0.0), 99.0) / 100.0

    @api.model
    def _plant_find_or_create(self, name, color=None, sequence=None):
        """The line called `name` (case-insensitive), created when it does not exist yet."""
        name = (name or "").strip()
        if not name:
            return self.browse()
        line = self.with_context(active_test=False).search([("name", "=ilike", name)], limit=1)
        if line:
            return line
        vals = {"name": name if name != name.upper() else name.title()}
        if color:
            vals["color"] = color
        if sequence is not None:
            vals["sequence"] = sequence
        else:
            last = self.search([], order="sequence desc, id desc", limit=1)
            vals["sequence"] = (last.sequence or 0) + 10
        return self.create(vals)

    def action_open_products(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("plant_request_board.action_plant_products")
        action["domain"] = [("plant_coffee_line_id", "=", self.id)]
        action["context"] = {"default_plant_coffee_line_id": self.id}
        return action
