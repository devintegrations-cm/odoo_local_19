from odoo import _, api, fields, models


class PlantProductFillWizard(models.TransientModel):
    """Planta › Clasificar productos: proposes the plant fields of the products from their names (the classifier),
    shows the proposal next to the current values so the plant can correct it, and writes it only on "Aplicar".
    Products applied this way count as reviewed (plant_manual)."""

    _name = "plant.product.fill.wizard"
    _description = "Clasificar productos para la planta"

    scope = fields.Selection([
        ("unclassified", "Productos sin clasificar"),
        ("auto", "Productos con clasificación automática (nadie los ha revisado)"),
        ("all", "Todos los productos"),
        ("selected", "Los productos seleccionados"),
    ], string="Qué productos", required=True, default="unclassified")
    product_tmpl_ids = fields.Many2many("product.template", string="Productos seleccionados")
    only_changes = fields.Boolean(string="Mostrar solo los que cambiarían", default=True)
    line_ids = fields.One2many("plant.product.fill.wizard.line", "wizard_id", string="Vista previa")
    line_count = fields.Integer(compute="_compute_counts")
    change_count = fields.Integer(compute="_compute_counts")
    state = fields.Selection([("choose", "Elegir"), ("preview", "Vista previa"), ("done", "Aplicado")], default="choose", readonly=True)
    applied_count = fields.Integer(readonly=True)

    @api.depends("line_ids", "line_ids.changed")
    def _compute_counts(self):
        for wiz in self:
            wiz.line_count = len(wiz.line_ids)
            wiz.change_count = len(wiz.line_ids.filtered("changed"))

    def _templates(self):
        self.ensure_one()
        Template = self.env["product.template"]
        if self.scope == "selected":
            return self.product_tmpl_ids
        domain = [("type", "!=", "service")]
        if self.scope == "unclassified":
            domain.append(("plant_kind_id", "=", False))
        elif self.scope == "auto":
            domain.append(("plant_manual", "=", False))
        return Template.search(domain, order="name")

    def action_preview(self):
        self.ensure_one()
        Template = self.env["product.template"]
        rules = Template._plant_parser_rules()
        lines = []
        for tmpl in self._templates():
            guess = tmpl._plant_guess(rules)
            kind = rules["kinds"][guess["kind"]]
            line = guess["line"]
            vals = {"plant_kind_id": kind.id, "plant_coffee_line_id": line.id if line else False, "plant_net_grams": guess["grams"], "plant_grind": guess["grind"], "plant_in_sheet": guess["in_sheet"]}
            changed = Template._plant_differs(tmpl, vals) or bool(not line and guess["line_name"])
            if self.only_changes and not changed:
                continue
            lines.append((0, 0, {
                "product_tmpl_id": tmpl.id, "kind_id": kind.id, "line_id": line.id if line else False, "line_name": "" if line else guess["line_name"],
                "grams": guess["grams"], "grind": guess["grind"], "in_sheet": guess["in_sheet"], "changed": changed,
            }))
        self.write({"line_ids": [(5, 0, 0)] + lines, "state": "preview"})
        return self._reopen()

    def action_apply(self):
        self.ensure_one()
        Line = self.env["plant.coffee.line"]
        applied = self.env["product.template"]
        for line in self.line_ids.filtered("apply"):
            coffee_line = line.line_id or (Line._plant_find_or_create(line.line_name) if line.line_name else Line)
            line.product_tmpl_id.with_context(plant_skip_reclassify=True).write({
                "plant_kind_id": line.kind_id.id, "plant_coffee_line_id": coffee_line.id if coffee_line else False,
                "plant_net_grams": line.grams, "plant_grind": line.grind, "plant_in_sheet": line.in_sheet, "plant_manual": True,
            })
            applied |= line.product_tmpl_id
        if applied:
            self.env["stock.move"]._plant_reclassify_open(applied)
        self.write({"state": "done", "applied_count": len(applied)})
        return self._reopen()

    def action_back(self):
        self.write({"state": "choose", "line_ids": [(5, 0, 0)]})
        return self._reopen()

    def _reopen(self):
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new", "name": _("Clasificar productos para la planta")}


class PlantProductFillWizardLine(models.TransientModel):
    _name = "plant.product.fill.wizard.line"
    _description = "Vista previa de la clasificación de un producto"
    _order = "changed desc, product_tmpl_id"

    wizard_id = fields.Many2one("plant.product.fill.wizard", required=True, ondelete="cascade")
    product_tmpl_id = fields.Many2one("product.template", string="Producto", required=True, readonly=True)
    default_code = fields.Char(related="product_tmpl_id.default_code", string="Referencia")
    apply = fields.Boolean(string="Aplicar", default=True)
    changed = fields.Boolean(string="Cambia", readonly=True)
    current_kind_id = fields.Many2one(related="product_tmpl_id.plant_kind_id", string="Tipo actual")
    current_line_id = fields.Many2one(related="product_tmpl_id.plant_coffee_line_id", string="Línea actual")
    current_grams = fields.Float(related="product_tmpl_id.plant_net_grams", string="Gramos actuales")
    current_grind = fields.Selection(related="product_tmpl_id.plant_grind", string="Molienda actual")
    kind_id = fields.Many2one("plant.kind", string="Tipo propuesto", required=True)
    line_id = fields.Many2one("plant.coffee.line", string="Línea propuesta")
    line_name = fields.Char(string="Línea nueva", help="Línea que el clasificador leyó en el nombre y todavía no existe: se crea al aplicar. Déjala vacía para no crearla.")
    grams = fields.Float(string="Gramos netos", digits=(12, 1))
    grind = fields.Selection(lambda self: self.env["product.template"]._fields["plant_grind"].selection, string="Molienda")
    in_sheet = fields.Boolean(string="Cuenta en consolidado")
