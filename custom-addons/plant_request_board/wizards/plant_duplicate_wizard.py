import re

from odoo import _, api, fields, models

CODE_FAMILY_RE = re.compile(r"^[A-Za-z]+")   # the letters a reference starts with: GEI200GENGRACAR → GEI, ROCJAV200G → ROCJAV


class PlantDuplicateWizard(models.TransientModel):
    """Planta › Duplicados: groups the products that look like the same reference (same coffee line, grams and
    grind, or the same name once the ignored words are removed), proposes a master for each group and writes
    plant_master_id on the others when the plant confirms. Nothing is deleted or archived: the variants keep
    existing and add up in their master.

    A name is not enough: when the internal references of a group start with different letters (GEI…, ROCJAV…,
    BAMA… under the same "GEISHA 200 G (copia)") or their bills of materials use different components, the group
    is marked "revisar a mano" and no master is proposed. The master proposed is the reference that moves most
    (done stock moves), then the one that appears in bills of materials."""

    _name = "plant.duplicate.wizard"
    _description = "Referencias duplicadas de la planta"

    scope = fields.Selection([("open", "Grupos sin resolver"), ("all", "Todos los grupos")], required=True, default="open",
                             help="Un grupo está resuelto cuando todas sus referencias ya suman en la misma maestra.")
    line_ids = fields.One2many("plant.duplicate.wizard.line", "wizard_id")
    group_count = fields.Integer(compute="_compute_counts")
    product_count = fields.Integer(compute="_compute_counts")
    state = fields.Selection([("choose", "Elegir"), ("preview", "Grupos"), ("done", "Aplicado")], default="choose", readonly=True)
    applied_count = fields.Integer(readonly=True)

    @api.depends("line_ids")
    def _compute_counts(self):
        for wiz in self:
            wiz.group_count = len(set(wiz.line_ids.mapped("group_seq")))
            wiz.product_count = len(wiz.line_ids)

    @api.model
    def _group_key(self, tmpl, own, rules):
        """Packed and bulk coffee: line × grams × grind. Anything else: the name without the ignored words."""
        if own["kind"] in ("packed", "prepare") and own["line_name"]:
            return ("coffee", own["kind"], own["line_name"].upper(), round(own["grams"] or 0.0, 1), own["grind"] or "")
        return ("name", own["kind"], self.env["product.template"]._plant_clean_name(tmpl.name, rules))

    @api.model
    def _group_label(self, key, rules):
        if key[0] == "coffee":
            kind, line, grams, grind = key[1:]
            parts = [line.title(), self.env["product.template"]._plant_size_text(grams), rules["grind_text"].get(grind, "")]
            return " · ".join(p for p in parts if p) + (" (granel)" if kind == "prepare" else "")
        return "Nombre: %s" % key[2]

    @api.model
    def _code_family(self, code):
        m = CODE_FAMILY_RE.match(code or "")
        return m.group(0).upper() if m else ""

    @api.model
    def _review_reason(self, members, bom_components):
        """Why a group must be reviewed by hand instead of taking the proposed master, or empty."""
        families = sorted({f for f in (self._code_family(m.default_code) for m in members) if f})
        if any(not (a.startswith(b) or b.startswith(a)) for a in families for b in families):
            return _("Referencias internas distintas: %s") % ", ".join(families)
        comps = {bom_components[m.id] for m in members if bom_components.get(m.id)}
        if len(comps) > 1:
            return _("Listas de materiales con componentes distintos")
        return ""

    @api.model
    def _bom_components(self, templates):
        """{template id: frozenset of component template ids of its first bill of materials}, when mrp is installed."""
        if "mrp.bom" not in self.env:
            return {}
        out = {}
        for bom in self.env["mrp.bom"].sudo().search([("product_tmpl_id", "in", templates.ids)], order="sequence, id"):
            out.setdefault(bom.product_tmpl_id.id, frozenset(bom.bom_line_ids.product_id.product_tmpl_id.ids))
        return out

    @api.model
    def _bom_presence(self, templates):
        """{template id: number of bills of materials where it is the product or a component}."""
        if "mrp.bom" not in self.env:
            return {}
        counts = {}
        for bom in self.env["mrp.bom"].sudo().search([("product_tmpl_id", "in", templates.ids)]):
            counts[bom.product_tmpl_id.id] = counts.get(bom.product_tmpl_id.id, 0) + 1
        for line in self.env["mrp.bom.line"].sudo().search([("product_id.product_tmpl_id", "in", templates.ids)]):
            tid = line.product_id.product_tmpl_id.id
            counts[tid] = counts.get(tid, 0) + 1
        return counts

    @api.model
    def _own_values(self, tmpl, rules):
        """The product's own classification (not its master's): fields when set, else the classifier."""
        if tmpl.plant_kind_id:
            return {"kind": tmpl.plant_kind_id.code, "line_name": tmpl.plant_coffee_line_id.name or "", "grams": tmpl.plant_net_grams, "grind": tmpl.plant_grind}
        return tmpl._plant_guess(rules)

    def action_scan(self):
        self.ensure_one()
        Template = self.env["product.template"]
        rules = Template._plant_parser_rules()
        rules["grind_text"] = {code: label.lower() for code, label in Template._fields["plant_grind"].selection}
        templates = Template.search([("type", "!=", "service")], order="id")
        groups = {}
        for tmpl in templates:
            groups.setdefault(self._group_key(tmpl, self._own_values(tmpl, rules), rules), []).append(tmpl)
        # how much each product has moved: the busiest reference is proposed as master
        moved = {}
        for product, count in self.env["stock.move"]._read_group([("state", "=", "done"), ("product_id.product_tmpl_id", "in", templates.ids)], ["product_id"], ["__count"]):
            moved[product.product_tmpl_id.id] = moved.get(product.product_tmpl_id.id, 0) + count
        candidates = Template.browse([m.id for members in groups.values() if len(members) > 1 for m in members])
        bom_components = self._bom_components(candidates)
        in_boms = self._bom_presence(candidates)
        lines, seq = [], 0
        for key, members in sorted(groups.items(), key=lambda item: str(item[0])):
            if len(members) < 2:
                continue
            roots = {(m.plant_master_id or m).id for m in members}
            if self.scope == "open" and len(roots) == 1 and len([m for m in members if not m.plant_master_id]) == 1:
                continue   # resolved: one master, every other member points to it
            reason = self._review_reason(members, bom_components)
            masters = [m for m in members if m.plant_variant_ids]
            suggested = masters[0] if masters else sorted(members, key=lambda m: (-moved.get(m.id, 0), -in_boms.get(m.id, 0), len(m.name or ""), m.id))[0]
            seq += 1
            for m in members:
                lines.append((0, 0, {
                    "group_seq": seq, "group": self._group_label(key, rules), "product_tmpl_id": m.id, "moves": moved.get(m.id, 0), "in_boms": in_boms.get(m.id, 0),
                    "review": bool(reason), "review_reason": reason or False, "apply": not reason,
                    "master_id": False if (reason or m == suggested) else suggested.id, "is_master": (m == suggested) and not reason,
                }))
        self.write({"line_ids": [(5, 0, 0)] + lines, "state": "preview"})
        return self._reopen()

    def action_apply(self):
        self.ensure_one()
        applied = self.env["product.template"]
        masters = self.line_ids.filtered(lambda l: l.apply and l.is_master).mapped("product_tmpl_id")
        masters.filtered("plant_master_id").with_context(plant_skip_reclassify=True).write({"plant_master_id": False})   # a master has no master
        for line in self.line_ids.filtered(lambda l: l.apply and l.master_id and l.master_id != l.product_tmpl_id):
            if line.product_tmpl_id.plant_master_id != line.master_id:
                line.product_tmpl_id.with_context(plant_skip_reclassify=True).write({"plant_master_id": line.master_id.id})
                applied |= line.product_tmpl_id
        if applied:
            self.env["stock.move"]._plant_reclassify_open(applied)
        self.write({"state": "done", "applied_count": len(applied)})
        return self._reopen()

    def action_back(self):
        self.write({"state": "choose", "line_ids": [(5, 0, 0)]})
        return self._reopen()

    def _reopen(self):
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new", "name": _("Referencias duplicadas")}


class PlantDuplicateWizardLine(models.TransientModel):
    _name = "plant.duplicate.wizard.line"
    _description = "Referencia de un grupo de posibles duplicados"
    _order = "group_seq, is_master desc, moves desc, id"

    wizard_id = fields.Many2one("plant.duplicate.wizard", required=True, ondelete="cascade")
    group_seq = fields.Integer(string="Grupo nº", readonly=True)
    group = fields.Char(string="Grupo", readonly=True)
    product_tmpl_id = fields.Many2one("product.template", string="Producto", required=True, readonly=True)
    default_code = fields.Char(related="product_tmpl_id.default_code", string="Referencia")
    product_active = fields.Boolean(related="product_tmpl_id.active", string="Activo")
    moves = fields.Integer(string="Movimientos hechos", readonly=True)
    in_boms = fields.Integer(string="En listas de materiales", readonly=True)
    review = fields.Boolean(string="Revisar a mano", readonly=True, help="El nombre coincide pero las referencias internas o las listas de materiales dicen que son productos distintos: no se propone maestra.")
    review_reason = fields.Char(string="Motivo", readonly=True)
    current_master_id = fields.Many2one(related="product_tmpl_id.plant_master_id", string="Maestra actual")
    is_master = fields.Boolean(string="Es la maestra", help="Las demás referencias del grupo suman en esta.")
    master_id = fields.Many2one("product.template", string="Suma en", help="Referencia maestra propuesta para esta referencia; vacío para dejarla como está.")
    apply = fields.Boolean(string="Aplicar", default=True)

    @api.onchange("is_master")
    def _onchange_is_master(self):
        if self.is_master:
            self.master_id = False
            for other in self.wizard_id.line_ids.filtered(lambda l: l.group_seq == self.group_seq and l != self):
                other.is_master = False
                other.master_id = self.product_tmpl_id
