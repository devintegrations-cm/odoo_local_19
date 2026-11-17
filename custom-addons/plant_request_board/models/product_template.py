import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

COFFEE_FIELDS = ("plant_coffee_variety", "plant_coffee_origin", "plant_coffee_process", "plant_roast_profile")
# the plant classification of a product; set by the classifier, the wizard or by hand
PLANT_FIELDS = ("plant_kind_id", "plant_coffee_line_id", "plant_net_grams", "plant_grind", "plant_in_sheet", "plant_master_id")
GRINDS = [("beans", "En grano"), ("ground", "Molido")]
GRIND_TEXT = {"beans": "en grano", "ground": "molido"}
# how a weight is read from a name: "PAZ 340 G", "2,5 KILOS", "2.27 KG", "10 OZ", "1 KILO" (structure, not vocabulary)
WEIGHT_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(KILOS?|KG|GRAMOS|GR|G|ONZAS?|OZ)\b")
OZ_GRAMS = 28.35


class ProductTemplate(models.Model):
    """What the plant needs to know about a product, as fields it can see and edit: how the line is counted
    (plant.kind), the coffee line, the net grams of the bag, the grind, whether it counts in the sheet and, for the
    duplicated references, the master product every variant adds up to.

    The fields are filled by the classifier when the product is created (from the name, with the vocabulary of
    Planta › Tipos de línea and Ajustes) and reviewed in Planta › Clasificar productos. From then on every
    calculation reads the fields, never the name. A product edited by hand (plant_manual) is left alone when the
    vocabulary changes; the automatic ones are classified again.

    Coffee master data (variety, origin, process, roast profile) lives here too: a product without its own values
    inherits them from the first coffee component of its bill of materials.
    """

    _inherit = "product.template"

    plant_kind_id = fields.Many2one("plant.kind", string="Tipo planta", index=True, ondelete="restrict", help="Cómo cuenta la planta este producto: granel en kg, bolsas por gramaje, listo para vender o insumo.")
    plant_kind_code = fields.Selection(related="plant_kind_id.code", string="Cómo se cuenta")
    plant_coffee_line_id = fields.Many2one("plant.coffee.line", string="Línea de café", index=True, ondelete="restrict")
    plant_net_grams = fields.Float(string="Gramos netos", digits=(12, 1), help="Gramos de café por unidad (bolsa de 340 g = 340). Cero para el café a granel y para los insumos.")
    plant_grind = fields.Selection(GRINDS, string="Molienda")
    plant_in_sheet = fields.Boolean(string="Cuenta en consolidado", help="Suma en las filas de la hoja de la planta y en el plan de tostión.")
    plant_master_id = fields.Many2one("product.template", string="Referencia maestra", index=True, ondelete="set null", domain="[('id', '!=', id), ('plant_master_id', '=', False)]", help="Producto equivalente al que suma este (la versión con código de barras suma en la versión sin código). Las variantes toman la línea, el gramaje y la molienda de la maestra.")
    plant_variant_ids = fields.One2many("product.template", "plant_master_id", string="Referencias equivalentes")
    plant_variant_count = fields.Integer(compute="_compute_plant_variant_count")
    plant_manual = fields.Boolean(string="Clasificación revisada", help="Marcado cuando alguien fijó los campos de planta a mano o en el asistente: un cambio del vocabulario no los toca.")
    plant_coffee_variety = fields.Char(string="Variedad", help="Variedad botánica: Castillo, Caturra, Geisha, Bourbon…")
    plant_coffee_origin = fields.Char(string="Origen", help="Región o finca: Huila, Nariño, Finca La Palma…")
    plant_coffee_process = fields.Selection([("lavado", "Lavado"), ("honey", "Honey"), ("natural", "Natural"), ("anaerobico", "Anaeróbico"), ("otro", "Otro")], string="Proceso")
    plant_roast_profile = fields.Char(string="Perfil de tueste", help="Claro, medio, oscuro, espresso, filtrado…")
    plant_coffee_summary = fields.Char(string="Ficha de café", compute="_compute_plant_coffee_summary", help="Variedad · origen · proceso · tueste, propios o heredados de la lista de materiales.")

    @api.constrains("plant_master_id")
    def _check_plant_master(self):
        for tmpl in self:
            if tmpl.plant_master_id and (tmpl.plant_master_id == tmpl or tmpl.plant_master_id.plant_master_id):
                raise ValidationError(_("La referencia maestra debe ser un producto que no tenga a su vez una referencia maestra."))

    @api.depends("plant_variant_ids")
    def _compute_plant_variant_count(self):
        for tmpl in self:
            tmpl.plant_variant_count = len(tmpl.plant_variant_ids)

    # --- the classifier: vocabulary from the database, structure in code --------------------------
    @api.model
    def _plant_parser_rules(self):
        """Everything the classifier compares a name with, loaded once per batch: the kinds and their words, the
        known coffee lines (records; a bulk product "… - X" names a new line through its suffix), the grind words
        and the words that are ignored (barcode mentions, copies). No search over the products."""
        Settings = self.env["res.config.settings"]
        kinds = self.env["plant.kind"]._by_code()
        lines = {line.name.upper(): line for line in self.env["plant.coffee.line"].search([])}
        return {
            "kinds": kinds,
            "words": {code: (kind._words(kind.keywords), kind._words(kind.category_keywords)) for code, kind in kinds.items()},
            "lines": sorted(lines.items(), key=lambda item: len(item[0]), reverse=True),   # longest first: COLD BREW before ROCK
            "beans": Settings._plant_get_list("plant_beans_words"),
            "ground": Settings._plant_get_list("plant_ground_words"),
            "ignore": Settings._plant_get_list("plant_ignore_words"),
        }

    @api.model
    def _plant_clean_name(self, name, rules):
        text = (name or "").upper()
        for word in rules["ignore"]:
            text = text.replace(word, " ")
        return re.sub(r"\s+", " ", text).strip()

    @api.model
    def _plant_grams_in(self, text):
        """(grams, match) of the first weight written in the text, or (0, None)."""
        m = WEIGHT_RE.search(text)
        if not m:
            return 0.0, None
        qty = float(m.group(1).replace(",", "."))
        unit = m.group(2)
        if unit.startswith("K"):
            return qty * 1000.0, m
        if unit.startswith("O"):
            return qty * OZ_GRAMS, m
        return qty, m

    def _plant_guess(self, rules=None):
        """What the name says: kind code, line (record or new name), grams, grind, in_sheet. Deterministic."""
        self.ensure_one()
        rules = rules or self._plant_parser_rules()
        name = self._plant_clean_name(self.name, rules)
        categ = (self.categ_id.complete_name or "").upper()

        def has(code, text=name, category=False):
            words = rules["words"].get(code, ((), ()))[1 if category else 0]
            return any(w in text for w in words)

        grams, m = self._plant_grams_in(name)
        line_rec, line_name, best = None, "", None
        for upper, rec in rules["lines"]:   # the line written first in the name wins ("DECAF PAZ 454 G" is Decaf); the longest on a tie
            m_line = re.search(r"\b" + re.escape(upper) + r"\b", name)
            if m_line and (best is None or m_line.start() < best):
                line_rec, line_name, best = rec, (rec.name if rec else upper.title()), m_line.start()
        supply = has("supply")
        green = has("green") or has("green", categ, category=True)   # unroasted coffee: never bulk, never in the sheet
        finished = has("packed", categ, category=True)   # the product category of the packed coffee
        by_weight = self.env["plant.sheet.row"]._is_weight(self.uom_id)
        prepare = not green and (has("prepare") or (by_weight and not supply and bool(line_name or finished)))   # roasted coffee sold by weight is bulk coffee
        ready = has("ready") and not supply and not green
        if not line_name and grams and finished and m and m.start() and not (supply or prepare or ready or green):
            line_name = name[: m.start()].strip(" -").title()   # single origins and blends in the finished-goods category: "B. AJI 340 G", "GEISHA 454 GR"
        if green:
            kind = "green"
        elif prepare:
            kind = "prepare"
            if not line_name and " - " in name:
                line_name = name.split(" - ")[-1].strip().title()   # "CAFE TOSTADO A GRANEL - B. ROJO"
        elif ready:
            kind = "ready"
        elif not supply and grams and (finished or line_name):   # a bag has a weight in its name; a drink or a kit has none
            kind = "packed"
        else:
            kind = "supply"
        grind = "ground" if any(w in name for w in rules["ground"]) else "beans" if any(w in name for w in rules["beans"]) else False
        return {
            "kind": kind, "line": line_rec if kind != "supply" else None, "line_name": line_name if kind != "supply" else "",
            "grams": grams if kind in ("packed", "ready") else 0.0, "grind": grind if kind in ("packed", "ready", "prepare") else False,
            "in_sheet": kind in ("prepare", "packed", "ready"),
        }

    def _plant_guess_vals(self, rules=None, create_lines=True):
        """The guess as write() values (the coffee line created when it is new and create_lines is set)."""
        guess = self._plant_guess(rules)
        line = guess["line"]
        if not line and guess["line_name"] and create_lines:
            line = self.env["plant.coffee.line"]._plant_find_or_create(guess["line_name"])
            if rules is not None:
                rules["lines"].append((line.name.upper(), line))
                rules["lines"].sort(key=lambda item: len(item[0]), reverse=True)
        return {
            "plant_kind_id": rules["kinds"][guess["kind"]].id if rules else self.env["plant.kind"]._by_code()[guess["kind"]].id,
            "plant_coffee_line_id": line.id if line else False, "plant_net_grams": guess["grams"], "plant_grind": guess["grind"], "plant_in_sheet": guess["in_sheet"],
        }

    @api.model
    def _plant_differs(self, record, vals):
        for name, value in vals.items():
            current = record[name]
            current = current.id if isinstance(current, models.BaseModel) else current
            if (current or False) != (value or False):
                return True
        return False

    def _plant_apply_guess(self, rules=None):
        """Classify these products from their names (automatic classification: plant_manual stays False); the open
        order lines of the products that changed follow."""
        rules = rules or self._plant_parser_rules()
        changed = self.browse()
        for tmpl in self:
            vals = tmpl._plant_guess_vals(rules)
            if self._plant_differs(tmpl, vals):
                tmpl.with_context(plant_auto=True, plant_skip_reclassify=True).write(vals)
                changed |= tmpl
        if changed and not self.env.context.get("plant_skip_reclassify"):
            self.env["stock.move"]._plant_reclassify_open(changed)
        return changed

    @api.model
    def _plant_reclassify_auto(self):
        """The vocabulary changed: the products nobody reviewed are classified again; the open order lines follow."""
        self.with_context(active_test=False).search([("plant_manual", "=", False)])._plant_apply_guess()

    # --- what the plant reads: the fields of the master product -----------------------------------
    def _plant_values(self, rules=None):
        """kind code, line record, grams, grind, in_sheet and the master product, from the fields (of the master
        when there is one). A product never classified is read from its name on the fly."""
        self.ensure_one()
        tmpl = self.plant_master_id or self
        if tmpl.plant_kind_id:
            return {"kind": tmpl.plant_kind_id.code, "kind_id": tmpl.plant_kind_id, "line": tmpl.plant_coffee_line_id, "line_name": tmpl.plant_coffee_line_id.name or "",
                    "grams": tmpl.plant_net_grams, "grind": tmpl.plant_grind, "in_sheet": tmpl.plant_in_sheet, "master": tmpl}
        guess = tmpl._plant_guess(rules)
        kind = (rules["kinds"] if rules else self.env["plant.kind"]._by_code()).get(guess["kind"])
        return {"kind": guess["kind"], "kind_id": kind, "line": guess["line"] or self.env["plant.coffee.line"], "line_name": guess["line_name"],
                "grams": guess["grams"], "grind": guess["grind"], "in_sheet": guess["in_sheet"], "master": tmpl}

    @api.model
    def _plant_size_text(self, grams):
        if not grams:
            return ""
        return ("%g kg" % (grams / 1000.0)) if grams >= 1000 else ("%g g" % grams)

    # --- automatic classification on create, manual flag on edit ------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        templates = super().create(vals_list)
        auto = templates.filtered(lambda t: not t.plant_kind_id)
        if auto:
            auto._plant_apply_guess()
        manual = templates - auto
        if manual:
            manual.with_context(plant_auto=True).write({"plant_manual": True})
        return templates

    def write(self, vals):
        plant_change = bool(vals.keys() & set(PLANT_FIELDS))
        if plant_change and not self.env.context.get("plant_auto"):
            vals = dict(vals, plant_manual=True)
        res = super().write(vals)
        if "name" in vals and not self.env.context.get("plant_auto"):
            renamed = self.filtered(lambda t: not t.plant_manual)
            if renamed:
                renamed._plant_apply_guess()
        if (plant_change or "name" in vals) and not self.env.context.get("plant_skip_reclassify"):
            self.env["stock.move"]._plant_reclassify_open(self)
        return res

    # --- coffee master data ---------------------------------------------------------------------
    def _plant_coffee_values(self, depth=2):
        """Own values, else the ones of the first coffee component in the bill of materials."""
        self.ensure_one()
        own = {f: self[f] for f in COFFEE_FIELDS}
        if any(own.values()) or depth <= 0 or "mrp.bom" not in self.env:
            return own
        bom = self.env["mrp.bom"].sudo()._bom_find(self.product_variant_id).get(self.product_variant_id) if self.product_variant_id else False
        for line in (bom.bom_line_ids if bom else []):
            component = line.product_id.product_tmpl_id
            if component._plant_values()["kind"] in ("prepare", "packed"):
                vals = component._plant_coffee_values(depth - 1)
                if any(vals.values()):
                    return vals
        return own

    @api.depends(*COFFEE_FIELDS)
    def _compute_plant_coffee_summary(self):
        labels = dict(self._fields["plant_coffee_process"].selection)
        for tmpl in self:
            vals = tmpl._plant_coffee_values()
            parts = [vals["plant_coffee_variety"], vals["plant_coffee_origin"], labels.get(vals["plant_coffee_process"]), vals["plant_roast_profile"]]
            tmpl.plant_coffee_summary = " · ".join(p for p in parts if p) or False

    def action_plant_open_variants(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("plant_request_board.action_plant_products")
        action["domain"] = [("plant_master_id", "=", self.id)]
        return action
