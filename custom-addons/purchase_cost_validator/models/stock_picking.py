import logging

from markupsafe import Markup

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)
PARAM_REVIEWER = "purchase_cost_validator.reviewer_user_id"
PARAM_HOLD = "purchase_cost_validator.hold_receipt"
ACTIVITY_PREFIX = "Revisar costo de la recepción"


class StockPicking(models.Model):
    _inherit = "stock.picking"

    cost_check_state = fields.Selection([("ok", "Sin novedad"), ("danger", "Desfase")], string="Revisión de costos", compute="_compute_cost_check_picking")
    cost_check_summary = fields.Char(string="Resumen de la revisión", compute="_compute_cost_check_picking")
    cost_alert = fields.Boolean(string="Desfase de costo", copy=False, readonly=True, index=True, tracking=True,
                                help="Al intentar recibir había un precio o una cantidad incoherente; se avisó al revisor de compras.")
    cost_alert_signature = fields.Char(copy=False, readonly=True, help="Lo que se le avisó al revisor, para no repetir el mismo aviso.")
    cost_approved_by = fields.Many2one("res.users", string="Desfase aprobado por", copy=False, readonly=True, tracking=True)

    # --- what is wrong in this receipt ------------------------------------------------
    def _cost_check_issues(self):
        """(purchase lines in red, extra rows) of an incoming receipt. Extra rows: receiving clearly more than what
        is pending on the order (a unit typed instead of a box, or a typo in the quantity)."""
        self.ensure_one()
        lines = self.env["purchase.order.line"]
        extra = []
        if self.picking_type_id.code != "incoming":
            return lines, extra
        start = self.env["purchase.order.line"]._cost_check_start()
        for move in self.move_ids.filtered(lambda m: m.state != "cancel"):
            pol = move.purchase_line_id
            if pol and not pol._cost_check_applies(start):
                continue   # order created before the go-live: left as it is
            if not pol and start and self.create_date and self.create_date < start:
                continue
            if pol and pol.cost_check_state == "danger":
                lines |= pol
            expected, done = move.product_uom_qty, move.quantity
            tolerance = (move.product_id.porcent_variation or 10.0) / 100.0
            if expected and done > expected * (1 + tolerance) and done - expected >= 1:
                extra.append((move.product_id.display_name, _("Se reciben %(done)g %(uom)s y en la orden quedan %(exp)g pendientes.", done=done, uom=move.product_uom.name, exp=expected)))
        return lines, extra

    @api.depends("move_ids.quantity", "move_ids.purchase_line_id.price_unit", "picking_type_id")
    def _compute_cost_check_picking(self):
        for picking in self:
            lines, extra = picking._cost_check_issues()
            n = len(lines) + len(extra)
            picking.cost_check_state = "danger" if n else "ok"
            names = [l.product_id.name for l in lines] + [e[0] for e in extra]
            picking.cost_check_summary = self.env["purchase.order"]._cost_check_names_list(names) if n else False

    # --- who reviews ------------------------------------------------------------------
    @api.model
    def _cost_check_reviewers(self):
        """The reviewer chosen in the settings; without one, the purchase managers, so the alert never goes nowhere."""
        uid = int(self.env["ir.config_parameter"].sudo().get_param(PARAM_REVIEWER) or 0)
        reviewer = self.env["res.users"].sudo().browse(uid).exists() if uid else self.env["res.users"]
        if reviewer:
            return reviewer
        group = self.env.ref("purchase.group_purchase_manager", raise_if_not_found=False)
        root = self.env.ref("base.user_root")
        # Odoo 19: user_ids solo trae a quien se puso a mano en el grupo; all_user_ids suma a quien lo hereda de otro
        # grupo, que es lo que devolvía group.users en 17
        return group.sudo().all_user_ids.filtered(lambda u: u.active and not u.share and u != root) if group else self.env["res.users"]

    def _cost_check_is_reviewer(self):
        return self.env.user in self._cost_check_reviewers() or self.env.user.has_group("stock.group_stock_manager")

    def _cost_check_notify(self, lines, extra):
        """Red flag + message to the reviewer (e-mail or Odoo inbox, as he has it set) + a to-do activity, and
        Telegram when the telegram_alerts module has a connector named "costos_compras". Once per problem."""
        self.ensure_one()
        signature = "|".join(sorted("%s:%s:%s:%s" % (l.id, l.price_unit, l.product_qty, l.product_uom_id.id) for l in lines) + sorted("%s:%s" % e for e in extra))
        self.sudo().cost_alert = True
        if signature == self.cost_alert_signature:
            return
        self.sudo().cost_alert_signature = signature
        reviewers = self._cost_check_reviewers()
        orders = self.move_ids.mapped("purchase_line_id.order_id")
        title = _("Recepción %(pick)s (%(orders)s, %(vendor)s): hay valores incoherentes que entrarían al costo del inventario. Revísala antes de recibir.",
                  pick=self.name, orders=", ".join(orders.mapped("name")) or "-", vendor=self.partner_id.display_name or "-")
        body = self.env["purchase.order"]._cost_check_table(lines, title, extra)
        self.sudo().message_post(body=body, partner_ids=reviewers.partner_id.ids, subtype_xmlid="mail.mt_note", message_type="comment")
        for user in reviewers:
            self.sudo().activity_schedule("mail.mail_activity_data_todo", user_id=user.id, summary="%s %s" % (ACTIVITY_PREFIX, self.name),
                                          note=body, date_deadline=fields.Date.context_today(self))
        if "telegram.alerts.config" in self.env:
            connector = self.env["telegram.alerts.config"].sudo().search([("identifier", "=", "costos_compras")], limit=1)
            if connector:
                text = title + "".join("\n- %s: %s" % (l.product_id.display_name, l.cost_check_message) for l in lines) + "".join("\n- %s: %s" % e for e in extra)
                try:
                    connector.send_alert(text)
                except Exception:  # noqa: BLE001 - an alert channel down must never stop the receipt
                    _logger.warning("Telegram alert for %s failed", self.name, exc_info=True)

    # --- reception ----------------------------------------------------------------------
    def button_validate(self):
        if self.env.context.get("cost_check_approved"):
            return super().button_validate()
        flagged = []
        for picking in self.filtered(lambda p: p.picking_type_id.code == "incoming" and p.state not in ("done", "cancel")):
            try:   # visual only: a failure of the check must never stop a receipt
                with self.env.cr.savepoint():
                    lines, extra = picking._cost_check_issues()
                    if lines or extra:
                        picking._cost_check_notify(lines, extra)
                        flagged.append((picking, lines, extra))
                    elif picking.cost_alert:
                        picking.sudo().cost_alert = False   # corrected before receiving: the red flag goes away
            except Exception:  # noqa: BLE001
                _logger.warning("Cost check of receipt %s failed; the receipt goes on", picking.name, exc_info=True)
        if not flagged:
            return super().button_validate()
        hold = self.env["ir.config_parameter"].sudo().get_param(PARAM_HOLD, "False") == "True"
        if not hold:   # the reviewer is already notified; the receipt goes on
            return super().button_validate()
        picking, lines, extra = flagged[0]
        names = ", ".join(self._cost_check_reviewers().mapped("name")) or _("el revisor de compras")
        message = self.env["purchase.order"]._cost_check_table(lines, _("Esta recepción tiene valores que dañarían el costo del inventario. Ya se le avisó a %s.", names), extra)
        can_approve = self._cost_check_is_reviewer()
        if can_approve:
            message += Markup("<p>%s</p>") % _("¿Recibir de todas formas? Quedará registrado que lo aprobaste con este desfase.")
        else:
            message += Markup("<p>%s</p>") % _("La recepción queda pendiente hasta que el revisor corrija la orden de compra o la apruebe. La mercancía no se pierde: solo falta confirmar el costo.")
        wizard = self.env["purchase.cost.review.wizard"].create({"picking_ids": [(6, 0, self.ids)], "message": message, "can_approve": can_approve})
        return {"type": "ir.actions.act_window", "name": _("Recepción con desfase de costo"), "res_model": wizard._name, "res_id": wizard.id, "view_mode": "form", "target": "new"}

    def _cost_check_approve(self):
        """The reviewer receives anyway: logged on the receipt, his activity closed, validation goes on."""
        for picking in self.filtered("cost_alert"):
            picking.sudo().cost_approved_by = self.env.user
            picking.message_post(body=_("Recepción aprobada con desfase de costo por %s.", self.env.user.name), subtype_xmlid="mail.mt_note")
            picking.activity_ids.filtered(lambda a: (a.summary or "").startswith(ACTIVITY_PREFIX)).action_feedback(feedback=_("Aprobada por %s", self.env.user.name))
        return self.with_context(cost_check_approved=True).button_validate()
