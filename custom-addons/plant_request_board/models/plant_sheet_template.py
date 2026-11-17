import math

from odoo import api, fields, models, tools

# the tabs and blocks of the workbook: structure (each tab has its own columns), read by plant.sheet from this field
SHEETS = [("tiendas", "PEDIDOS TIENDAS"), ("otros", "OTROS PEDIDOS"), ("attenza", "ATTENZA")]
BLOCKS = [("coffee", "Café (bolsas y preparación)"), ("ready", "Cápsulas y drips")]


class PlantSheetRow(models.Model):
    """One row of the plant's workbook. Automatic rows (is_auto) are generated from the plant fields of the
    products, one per coffee line × grams × grind ("Paz 340 en grano", "Paz Preparación 2.5") and one per ready
    product, and refreshed every time the sheet is opened; the plant may still type their INVENTARIO or archive
    them. Manual rows are kept for the kits (a kit row with component rows and factors) and for exceptions: a
    manual row with products and the "exception" flag takes those products away from their automatic row. Rows
    stay visible when empty, like in the workbook."""

    _name = "plant.sheet.row"
    _description = "Fila de la hoja de la planta"
    _order = "sheet, sequence, id"

    sheet = fields.Selection(SHEETS, string="Pestaña", required=True, default="tiendas", index=True)
    block = fields.Selection(BLOCKS, string="Bloque", required=True, default="coffee")
    sequence = fields.Integer(default=10)
    line = fields.Char(string="Línea de café", help="Agrupa las filas para el TOTAL NETO X TOSTAR (Paz, Libre, Punk…).")
    line_id = fields.Many2one("plant.coffee.line", string="Línea", ondelete="set null", help="Línea de café de la fila automática.")
    is_auto = fields.Boolean(string="Automática", readonly=True, help="Generada desde los campos de planta de los productos; se actualiza sola.")
    auto_key = fields.Char(string="Clave automática", readonly=True, index=True)
    exception = fields.Boolean(string="Excepción", default=True, help="Los productos de esta fila manual suman aquí y no en su fila automática. Sin esta marca la fila manual no interviene en la hoja.")
    name = fields.Char(string="Ítem", required=True, help="Texto tal como aparece en la hoja de la planta.")
    color = fields.Char(string="Color", default="#FFFFFF", help="Color de fondo del ítem, en hexadecimal (#FFE599). Es el color de la línea de café en la hoja de la planta.")
    net_color = fields.Char(string="Color total neto", help="Color de la celda TOTAL NETO X TOSTAR de la línea, si es distinto al de la fila (en OTROS PEDIDOS el grupo PAZ usa #B6D7A8).")
    grams = fields.Float(string="Gramos por unidad", digits=(12, 1), help="Gramaje de la bolsa: 200, 340, 454, 2500… Es el factor de TOSTAR = gramos × por fabricar / 1000. Cero para cápsulas y drips.")
    product_ids = fields.Many2many("product.product", "plant_sheet_row_product_rel", "row_id", "product_id", string="Productos de Odoo", context={"active_test": False}, help="Lo pedido de cualquiera de estos productos suma en la fila. Los productos en gramos se convierten con el gramaje.")
    product_codes = fields.Char(string="Referencias", help="Referencias internas separadas por coma; «Vincular productos» busca estos códigos y llena los productos.")
    parent_id = fields.Many2one("plant.sheet.row", string="Componente de", ondelete="cascade", help="Para los kits de Attenza: esta fila es un componente del kit y recibe su cantidad × factor.")
    child_ids = fields.One2many("plant.sheet.row", "parent_id")
    factor = fields.Float(string="Unidades por kit", default=1.0)
    units_per_box = fields.Integer(string="Unidades por caja", help="Attenza: CAJAS = total ÷ unidades por caja, redondeado hacia arriba.")
    inventory_manual = fields.Float(string="Inventario digitado", digits=(12, 2), help="Si la planta prefiere digitar el inventario de esta fila, se usa este valor en vez de las existencias de Odoo.")
    inventory_manual_date = fields.Date(string="Digitado el")
    note = fields.Char(string="Nota", help="Marca o comentario que aparece junto a la fila (el «*» de la hoja).")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    _factor_positive = models.Constraint("CHECK(factor > 0)", "El factor del componente debe ser mayor que cero.")

    @api.model
    def _codes(self, raw):
        return [c.strip() for c in (raw or "").split(",") if c.strip()]

    def action_link_products(self):
        """Fill product_ids from product_codes (exact internal reference). Missing codes are left out quietly."""
        Product = self.env["product.product"].with_context(active_test=False)
        for row in self:
            codes = row._codes(row.product_codes)
            if not codes:
                continue
            found = Product.search([("default_code", "in", codes)])
            if found:
                row.product_ids = [(6, 0, found.ids)]
        return True

    def action_clear_manual_inventory(self):
        self.write({"inventory_manual": 0.0, "inventory_manual_date": False})
        return True

    def _plant_is_kit_part(self):
        self.ensure_one()
        return bool(self.parent_id or self.child_ids)

    @api.model
    def _plant_bootstrap_from_rows(self):
        """Carry the knowledge of the legacy manual rows (1.4.0 and before) into records once: the coffee lines
        (name, order and colour of each line), the plant fields of every product a row listed (line, grams, kind,
        in sheet), and the exception flag (kits keep it, plain rows become inert). Used by the 1.5.0 migration and
        by a fresh install, where the seeded rows define the lines."""
        Line = self.env["plant.coffee.line"]
        Template = self.env["product.template"]
        rows = self.with_context(active_test=False).search([("sheet", "in", [code for code, _label in SHEETS])], order="sheet desc, sequence, id")   # tiendas first
        lines, seq = {}, 0
        for row in rows:
            key = (row.line or "").strip().upper()
            if key and key not in lines and not row._plant_is_kit_part():   # a kit's "line" is the kit's name, not a coffee line
                seq += 10
                lines[key] = Line._plant_find_or_create(row.line.strip(), color=row.color if row.block == "coffee" or row.block == "ready" else None, sequence=seq)
                if row.net_color and not lines[key].net_color:
                    lines[key].net_color = row.net_color
        rules = Template._plant_parser_rules()
        done = set()
        for row in rows:
            if row.child_ids or not row.product_ids:
                continue
            line = lines.get((row.line or "").strip().upper())
            for tmpl in row.product_ids.product_tmpl_id:
                if tmpl.id in done:
                    continue
                done.add(tmpl.id)
                guess = tmpl._plant_guess(rules)
                if row.block == "ready":
                    kind = "ready"
                elif any(self._is_weight(p.uom_id) for p in tmpl.product_variant_ids):
                    kind = "prepare"
                else:
                    kind = "packed"
                tmpl.with_context(plant_auto=True, plant_skip_reclassify=True).write({
                    "plant_kind_id": rules["kinds"][kind].id, "plant_coffee_line_id": line.id if line else False,
                    "plant_net_grams": row.grams if kind != "prepare" else 0.0, "plant_grind": guess["grind"], "plant_in_sheet": True, "plant_manual": True,
                })
        for row in rows:
            if row.exception and not row._plant_is_kit_part():
                row.exception = False
        return rows

    # --- quantities ----------------------------------------------------------------
    @api.model
    @tools.ormcache()
    def _plant_gram_refs(self):
        """(id of the gram unit, key of the weight units) resolved once per registry: env.ref() queries the
        database every time, and the sheet asks for thousands of units per load. Odoo 17 groups the units by
        category; Odoo 19 has no categories, so the key is the root of the chain of reference units."""
        gram = self.env.ref("uom.product_uom_gram", raise_if_not_found=False)
        if not gram:
            return (False, False)
        return (gram.id, gram.category_id.id if "category_id" in gram._fields else self._uom_root(gram).id)

    @api.model
    def _uom_root(self, uom):
        seen = set()
        while getattr(uom, "relative_uom_id", False) and uom.id not in seen:
            seen.add(uom.id)
            uom = uom.relative_uom_id
        return uom

    def _is_weight(self, uom):
        """Grams, kilos and the other weight units (same category as the gram, or the same root in Odoo 19)."""
        gram_id, key = self._plant_gram_refs()
        if not uom or not gram_id:
            return False
        return (uom.category_id.id if "category_id" in uom._fields else self._uom_root(uom).id) == key

    @api.model
    def _plant_gram(self):
        return self.env["uom.uom"].browse(self._plant_gram_refs()[0])

    def _units(self, product, qty, uom):
        """Units of this row for qty of product: grams and kilos are divided by the row's grams, pieces count as is."""
        self.ensure_one()
        if self._is_weight(uom):
            grams = uom._compute_quantity(qty, self._plant_gram(), round=False)
            return grams / self.grams if self.grams else grams / 1000.0
        return qty

    def _boxes(self, total):
        return math.ceil(total / self.units_per_box) if self.units_per_box and total > 0 else None

    def _lots(self, locations):
        """Lots at the plants shown for the row's products, with the nearest expiry (only when products are tracked)."""
        self.ensure_one()
        tracked = self.product_ids.filtered(lambda p: p.tracking != "none")
        if not tracked or not locations:
            return "", ""
        quants = self.env["stock.quant"].search([("product_id", "in", tracked.ids), ("location_id", "child_of", locations.ids), ("quantity", ">", 0), ("lot_id", "!=", False)])
        lots = quants.mapped("lot_id")
        names = ", ".join(sorted(set(lots.mapped("name"))))
        expiry = ""
        if "expiration_date" in lots._fields:
            dates = [l.expiration_date for l in lots if l.expiration_date]
            expiry = min(dates).strftime("%Y-%m-%d") if dates else ""
        return names, expiry


class PlantSheetColumn(models.Model):
    """Optional layer over the store columns of PEDIDOS TIENDAS: the plant's short name (ZONA G, 79, 85…), its
    order, its colour, and whether it is hidden. EVENTO is one of these and groups every event warehouse. Every
    other store (stock.warehouse flagged "Es tienda") and every warehouse that orders gets its column by itself."""

    _name = "plant.sheet.column"
    _description = "Columna de la hoja de la planta"
    _order = "sheet, sequence, id"

    sheet = fields.Selection(SHEETS, string="Pestaña", required=True, default="tiendas")
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Encabezado", required=True)
    header_color = fields.Char(string="Color del encabezado", default="#2F5496", help="Azul de la hoja: #2F5496; LAURELES y SPC #1C4587; SURA #0B5394.")
    warehouse_ids = fields.Many2many("stock.warehouse", "plant_sheet_column_warehouse_rel", "column_id", "warehouse_id", string="Almacenes", context={"active_test": False})
    warehouse_codes = fields.Char(string="Códigos de almacén", help="Códigos separados por coma; «Vincular almacenes» los busca y llena los almacenes.")
    hidden = fields.Boolean(string="Oculta", help="La columna no se dibuja en la hoja ni en el Excel; lo que piden sus almacenes sigue sumando en TOTAL BOLSAS.")
    active = fields.Boolean(default=True)

    def action_link_warehouses(self):
        Warehouse = self.env["stock.warehouse"].with_context(active_test=False)
        for col in self:
            codes = [c.strip() for c in (col.warehouse_codes or "").split(",") if c.strip()]
            if codes:
                found = Warehouse.search([("code", "in", codes)])
                if found:
                    col.warehouse_ids = [(6, 0, found.ids)]
        return True
