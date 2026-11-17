from markupsafe import Markup, escape

from odoo import _, fields, models


class PlantValidateWizard(models.TransientModel):
    """Explicit confirmation before "Validar entrega" when the request is not ready to be validated at once: the
    lines without a quantity (they would be delivered in full) and the lines short of stock at the plant. The
    plant reads, decides, and either delivers in full or goes back to set the quantities."""

    _name = "plant.validate.wizard"
    _description = "Confirmar la validación de una entrega de planta"

    picking_id = fields.Many2one("stock.picking", required=True, readonly=True)
    missing_html = fields.Html(string="Líneas sin cantidad", readonly=True, sanitize=False)
    shortage_html = fields.Html(string="Sin stock suficiente", readonly=True, sanitize=False)
    has_missing = fields.Boolean(readonly=True)
    has_shortage = fields.Boolean(readonly=True)
    progress_text = fields.Char(readonly=True)

    def _open_for(self, picking, issues):
        Picking = self.env["stock.picking"]
        missing = Markup("").join(Markup("<li><b>%s</b>: %s pedido, sin cantidad hecha</li>") % (escape(mv.product_id.display_name), Picking._plant_qty_text(mv, mv.product_uom_qty)) for mv in issues["missing"])
        shortage = Markup("").join(Markup("<li><b>%s</b>: %s pedido, %s en stock</li>") % (escape(mv.product_id.display_name), Picking._plant_qty_text(mv, demand), Picking._plant_qty_text(mv, available)) for mv, demand, available in issues["shortages"])
        wizard = self.create({
            "picking_id": picking.id,
            "missing_html": Markup("<ul>%s</ul>") % missing if missing else False,
            "shortage_html": Markup("<ul>%s</ul>") % shortage if shortage else False,
            "has_missing": bool(issues["missing"]), "has_shortage": bool(issues["shortages"]),
            "progress_text": _("%s de %s líneas chuleadas (%s %%)") % (picking.plant_check_done, picking.plant_check_count, int(picking.plant_progress)),
        })
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": wizard.id, "view_mode": "form", "target": "new", "name": _("Validar entrega · %s") % picking.name}

    def action_confirm(self):
        self.ensure_one()
        return self.picking_id.with_context(plant_validate_confirmed=True).action_plant_validate()
