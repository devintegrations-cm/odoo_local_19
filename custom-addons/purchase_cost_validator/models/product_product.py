import logging

from markupsafe import Markup

from odoo import _, api, models

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    """Warns when somebody types a product cost that jumps by an incoherent factor (a kilo typed as a gram, a box as
    a unit). Visual only: the cost the person saves is never changed, delayed or refused, and any failure here is
    logged and swallowed. Automatic recalculations of the average cost are not manual edits and are ignored."""

    _inherit = "product.product"

    @api.model
    def _cost_edit_message(self, old, new):
        """Text when the change old -> new is incoherent, else False. A first cost (old = 0) is never flagged."""
        if not old or old <= 0:
            return False
        gross = self.env["purchase.order.line"]._cost_check_settings()["gross"]
        if new <= 0:
            return _("El costo pasa de %s a cero: el inventario de este producto quedaría sin valor.", self._cost_edit_money(old))
        ratio = new / old
        if ratio < gross and ratio > 1.0 / gross:
            return False
        how = _("%s veces más alto", ("%.0f" if ratio >= 10 else "%.1f") % ratio) if ratio >= 1 else _("%s veces más bajo", ("%.0f" if ratio <= 0.1 else "%.1f") % (1 / ratio))
        big = ratio if ratio >= 1 else 1.0 / ratio
        hint = _(" ¿Está en la unidad correcta (gramos o kilos, unidad o caja)?") if any(abs(big / f - 1.0) <= 0.15 for f in (6, 10, 12, 20, 24, 25, 50, 100, 500, 1000)) else ""
        return _("El costo pasa de %(old)s a %(new)s, %(how)s.%(hint)s", old=self._cost_edit_money(old), new=self._cost_edit_money(new), how=how, hint=hint)

    @api.model
    def _cost_edit_money(self, amount):
        from odoo.tools import formatLang
        return formatLang(self.env, amount, currency_obj=self.env.company.currency_id)

    def write(self, vals):
        old = {}
        if "standard_price" in vals and not self.env.context.get("disable_auto_revaluation") and not self.env.context.get("disable_auto_svl") and not self.env.context.get("install_mode"):
            try:
                old = {p.id: p.standard_price for p in self}
            except Exception:  # noqa: BLE001 - never let the check touch the save
                old = {}
        result = super().write(vals)
        if old:
            try:
                with self.env.cr.savepoint():
                    self._cost_edit_notify(old)
            except Exception:  # noqa: BLE001
                _logger.warning("Cost edit check failed; the cost was saved as typed", exc_info=True)
        return result

    def _cost_edit_notify(self, old):
        for product in self:
            before, after = old.get(product.id), product.standard_price
            message = self._cost_edit_message(before, after)
            if not message:
                continue
            qty = max(product.sudo().qty_available, 0.0)
            impact = abs(after - before) * qty
            extra = _(" Afecta unos %(impact)s del valor del inventario (%(qty)g en existencia).", impact=self._cost_edit_money(impact), qty=qty) if impact else ""
            reviewers = self.env["stock.picking"]._cost_check_reviewers()
            title = _("Cambio de costo incoherente en %(prod)s, hecho por %(user)s.", prod=product.display_name, user=self.env.user.name)
            body = Markup("<p><b>%s</b></p><p>%s%s</p><p>%s</p>") % (title, message, extra, _("El costo quedó guardado como se digitó. Revísalo si no era lo esperado."))
            template = product.product_tmpl_id.sudo()
            template.message_post(body=body, partner_ids=reviewers.partner_id.ids, subtype_xmlid="mail.mt_note", message_type="comment")
            for user in reviewers:
                template.activity_schedule("mail.mail_activity_data_todo", user_id=user.id, summary=_("Revisar cambio de costo de %s", product.display_name), note=body)
            if "telegram.alerts.config" in self.env:
                connector = self.env["telegram.alerts.config"].sudo().search([("identifier", "=", "costos_compras")], limit=1)
                if connector:
                    try:
                        connector.send_alert("%s\n%s%s" % (title, message, extra))
                    except Exception:  # noqa: BLE001
                        _logger.warning("Telegram alert for cost edit failed", exc_info=True)
