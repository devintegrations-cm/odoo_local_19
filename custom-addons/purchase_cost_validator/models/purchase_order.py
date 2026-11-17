import logging

from markupsafe import Markup

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)
CELL = "padding:4px 8px;border:1px solid #ddd"


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    cost_check_state = fields.Selection([("ok", "Sin novedad"), ("warning", "Revisar"), ("danger", "Desfase")], string="Revisión de costos", compute="_compute_cost_check_order")
    cost_check_count = fields.Integer(string="Líneas por revisar", compute="_compute_cost_check_order")
    cost_check_summary = fields.Char(string="Resumen de la revisión", compute="_compute_cost_check_order")
    cost_alert = fields.Boolean(string="Desfase de costo", copy=False, readonly=True, index=True, tracking=True,
                                help="La orden se confirmó con un desfase de costo incoherente (precio en cero, o más del doble o menos de la mitad de lo esperado).")

    @api.depends("order_line.price_unit", "order_line.product_qty", "order_line.product_uom_id", "order_line.product_id")
    def _compute_cost_check_order(self):
        for order in self:
            red = order.order_line.filtered(lambda l: l.cost_check_state == "danger")
            yellow = order.order_line.filtered(lambda l: l.cost_check_state == "warning")
            order.cost_check_state = "danger" if red else ("warning" if yellow else "ok")
            order.cost_check_count = len(red) + len(yellow)
            lines = red or yellow
            order.cost_check_summary = order._cost_check_names_list(lines.mapped("product_id.name")) if lines else False

    @api.model
    def _cost_check_names_list(self, names, shown=3):
        """"FILTRO CHEMEX", "FILTRO CHEMEX y AJO", "FILTRO CHEMEX, AJO, AZUCAR y 2 más"."""
        names = list(dict.fromkeys(n for n in names if n))
        if len(names) <= 1:
            return names[0] if names else ""
        if len(names) <= shown:
            return ", ".join(names[:-1]) + " y " + names[-1]
        return ", ".join(names[:shown]) + " y %s más" % (len(names) - shown)

    def button_confirm(self):
        """Never blocks. Once confirmed, incoherent lines are flagged and written in the chatter."""
        result = super().button_confirm()
        for order in self.filtered(lambda o: o.state in ("purchase", "done")):
            try:   # the order is already confirmed: the note is a courtesy and can never undo it
                with self.env.cr.savepoint():
                    order._cost_check_log_confirmation()
            except Exception:  # noqa: BLE001
                _logger.warning("Cost check note for %s failed", order.name, exc_info=True)
        return result

    def _continue_confirmation(self):
        """purchase_price_validation (when it is installed next to this module and its checks are on) confirms the
        order through its own dialog, which calls this method and skips button_confirm. The validator listens there
        too, so both modules coexist: the old one keeps its dialog and this one still flags the order and writes its
        note. Without that module nobody calls this method."""
        parent = getattr(super(), "_continue_confirmation", None)
        result = parent() if parent else None
        for order in self.filtered(lambda o: o.state in ("purchase", "done")):
            try:
                with self.env.cr.savepoint():
                    order._cost_check_log_confirmation()
            except Exception:  # noqa: BLE001 - the order is already confirmed: the note can never undo it
                _logger.warning("Cost check note for %s failed", order.name, exc_info=True)
        return result

    def _cost_check_log_confirmation(self):
        self.ensure_one()
        bad = self.order_line.filtered(lambda l: l.cost_check_state == "danger")
        if not bad:
            return
        self.cost_alert = True
        reviewers = self.env["stock.picking"]._cost_check_reviewers()
        title = _("Orden %(order)s (%(vendor)s) confirmada con desfase de costo. Revísala: si se recibe así, se daña el costo del inventario.",
                  order=self.name, vendor=self.partner_id.display_name or "-")
        body = self._cost_check_table(bad, title)
        # the reviewer is told now (e-mail or Odoo inbox, as he has it set) and gets a to-do; if it is still wrong at the
        # receipt, the receipt warns again
        self.sudo().message_post(body=body, partner_ids=reviewers.partner_id.ids, subtype_xmlid="mail.mt_note", message_type="comment")
        for user in reviewers:
            self.sudo().activity_schedule("mail.mail_activity_data_todo", user_id=user.id, summary="Revisar costo de la orden %s" % self.name,
                                   note=body, date_deadline=fields.Date.context_today(self))

    @api.model
    def _cost_check_table(self, lines, title, extra_rows=None):
        """HTML table for the chatter, the reviewer's message and the review window."""
        rows = Markup("")
        for line in lines:
            rows += Markup("<tr><td style='%s'>%s</td><td style='%s;text-align:right;white-space:nowrap'>%s %s</td><td style='%s;text-align:right;white-space:nowrap;color:#c00;font-weight:bold'>%s</td>"
                           "<td style='%s;text-align:right;white-space:nowrap'>%s</td><td style='%s'>%s</td></tr>") % (
                CELL, line.product_id.display_name, CELL, "%g" % line.product_qty, line.product_uom_id.name, CELL, line._cost_check_money(line.price_unit),
                CELL, line._cost_check_money(line.cost_check_reference) if line.cost_check_reference else "—", CELL, line.cost_check_message or "")
        for name, text in extra_rows or []:
            rows += Markup("<tr><td style='%s'>%s</td><td colspan='4' style='%s;color:#c00'>%s</td></tr>") % (CELL, name, CELL, text)
        head = Markup("<tr style='background:#f5f5f5'><th style='%s;text-align:left'>Producto</th><th style='%s;white-space:nowrap'>Cantidad</th><th style='%s;white-space:nowrap'>Precio digitado</th>"
                      "<th style='%s;white-space:nowrap'>Esperado</th><th style='%s;text-align:left'>Detalle</th></tr>") % (CELL, CELL, CELL, CELL, CELL)
        return Markup("<p><b>%s</b></p><table style='width:100%%;border-collapse:collapse;font-size:13px'>%s%s</table>") % (title, head, rows)
