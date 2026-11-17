# -*- coding: utf-8 -*-
"""Cost check of every purchase line, before it becomes inventory cost.

The price the store typed is compared, in the same unit of measure and currency, with the rules already in the
system: the product's cost (standard_price) and its "Variación de Costo" (porcent_variation, 10 % by default):

- ok       within the product tolerance
- warning  beyond the product tolerance (the rule the module always had): shown in yellow, nothing else
- danger   incoherent: more than GROSS times or less than 1/GROSS of the reference (20 milks for 1 000 000,
           a box typed as a unit), or a price of zero. Shown in red; at reception the reviewer is notified.

Nothing here blocks typing an order.
"""
import logging

from odoo import _, api, fields, models
from odoo.tools import float_is_zero, formatLang

_logger = logging.getLogger(__name__)
PARAM_GROSS = "purchase_cost_validator.gross_factor"
PARAM_START = "purchase_cost_validator.start_date"
STATES = [("ok", "Sin novedad"), ("warning", "Revisar"), ("danger", "Desfase"), ("none", "Sin referencia")]


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    cost_check_state = fields.Selection(STATES, string="Revisión de costo", compute="_compute_cost_check", help="Comparación del precio con lo que suele costar el producto, en la misma unidad de medida.")
    cost_check_reference = fields.Monetary(string="Precio de referencia", compute="_compute_cost_check", currency_field="currency_id", help="Costo del producto expresado en la unidad y la moneda de esta línea.")
    cost_check_deviation = fields.Float(string="Desfase (%)", compute="_compute_cost_check", digits=(16, 1))
    cost_check_message = fields.Char(string="Detalle de la revisión", compute="_compute_cost_check")
    cost_check_field = fields.Selection([("price", "Precio"), ("quantity", "Cantidad o unidad")], string="Campo a revisar", compute="_compute_cost_check",
                                        help="Dónde está el error probable: el precio, o la cantidad / unidad de medida cuando el desfase es un múltiplo típico de empaque (×10, ×12, ×100, ×1000).")

    # --- settings -----------------------------------------------------------------
    @api.model
    def _cost_check_settings(self):
        icp = self.env["ir.config_parameter"].sudo()
        def num(key, default):
            try:
                return float(icp.get_param(key) or default)
            except (TypeError, ValueError):
                return default
        return {"gross": max(num(PARAM_GROSS, 2.0), 1.01)}

    # --- only what is new ----------------------------------------------------------------
    @api.model
    def _cost_check_start(self):
        """Go-live of the validator: orders created before it are left exactly as they are."""
        raw = self.env["ir.config_parameter"].sudo().get_param(PARAM_START)
        try:
            return fields.Datetime.to_datetime(raw) if raw else False
        except (TypeError, ValueError):
            return False

    @api.model
    def _cost_check_set_start_if_missing(self):
        if not self._cost_check_start():
            self.env["ir.config_parameter"].sudo().set_param(PARAM_START, fields.Datetime.to_string(fields.Datetime.now()))

    def _cost_check_applies(self, start=None):
        """New orders only. An order still being typed has no creation date yet: it is new."""
        self.ensure_one()
        start = self._cost_check_start() if start is None else start
        created = self.order_id.create_date
        return not (start and created and created < start)

    # --- unit and currency conversions ----------------------------------------------------
    def _cost_check_unit_price(self, price=None):
        """Price per product unit (not per box or dozen), in company currency."""
        self.ensure_one()
        price = self.price_unit if price is None else price
        order = self.order_id
        if self.product_uom_id and self.product_id and self.product_uom_id != self.product_id.uom_id:
            price = self.product_uom_id._compute_price(price, self.product_id.uom_id)
        company = order.company_id or self.env.company
        if order.currency_id and order.currency_id != company.currency_id:
            price = order.currency_id._convert(price, company.currency_id, company, order.date_order or fields.Date.today(), round=False)
        return price

    def _cost_check_to_line_price(self, unit_price):
        """Back from price per product unit in company currency to the unit and currency of this line."""
        self.ensure_one()
        order = self.order_id
        company = order.company_id or self.env.company
        price = unit_price
        if order.currency_id and order.currency_id != company.currency_id:
            price = company.currency_id._convert(price, order.currency_id, company, order.date_order or fields.Date.today(), round=False)
        if self.product_uom_id and self.product_id and self.product_uom_id != self.product_id.uom_id:
            price = self.product_id.uom_id._compute_price(price, self.product_uom_id)
        return price

    # --- the check ------------------------------------------------------------------
    @api.depends("product_id", "product_qty", "product_uom_id", "price_unit", "order_id.currency_id", "display_type")
    def _compute_cost_check(self):
        start = self._cost_check_start()
        lines = self.filtered(lambda l: not l.display_type and l.product_id and l.product_id.type == "consu" and l._cost_check_applies(start))
        (self - lines).update({"cost_check_state": False, "cost_check_reference": 0.0, "cost_check_deviation": 0.0, "cost_check_message": False, "cost_check_field": False})
        if not lines:
            return
        settings = self._cost_check_settings()
        for line in lines:
            try:   # opening or typing an order must never fail because of the check
                line.update(line._cost_check_eval(settings))
            except Exception:  # noqa: BLE001
                _logger.warning("Cost check of purchase line %s failed", line.id, exc_info=True)
                line.update({"cost_check_state": False, "cost_check_reference": 0.0, "cost_check_deviation": 0.0, "cost_check_message": False, "cost_check_field": False})

    def _cost_check_eval(self, settings):
        self.ensure_one()
        product = self.product_id
        tolerance = product.porcent_variation or 10.0
        reference = product.standard_price if product.standard_price > 0 else 0.0
        source = _("costo del producto")
        ref_line = self._cost_check_to_line_price(reference) if reference else 0.0
        out = {"cost_check_reference": ref_line, "cost_check_deviation": 0.0, "cost_check_field": "price"}
        if float_is_zero(self.price_unit, precision_digits=6):
            out.update(cost_check_state="danger", cost_check_message=_("El precio está en cero: el producto entraría al inventario sin costo."))
            return out
        if not reference:
            out.update(cost_check_state="none", cost_check_message=_("El producto no tiene costo registrado: no hay con qué comparar."))
            return out
        unit_price = self._cost_check_unit_price()
        ratio = unit_price / reference
        deviation = (ratio - 1.0) * 100.0
        out["cost_check_deviation"] = deviation
        uom = self.product_uom_id.name or ""
        if ratio >= settings["gross"] or ratio <= 1.0 / settings["gross"]:
            if self._cost_check_looks_like_unit(ratio):
                out["cost_check_field"] = "quantity"
            hint = _(" ¿La unidad de medida o la cantidad son las correctas?") if (ratio >= 5 or ratio <= 0.2) else ""
            how = _("%s veces más caro", "%.0f" % ratio if ratio >= 10 else "%.1f" % ratio) if ratio >= 1 else _("%s veces más barato", "%.0f" % (1 / ratio) if ratio <= 0.1 else "%.1f" % (1 / ratio))
            out.update(cost_check_state="danger", cost_check_message=_("%(how)s que el costo: %(price)s por %(uom)s frente a %(ref)s del %(src)s.%(hint)s",
                                                                       how=how, price=self._cost_check_money(self.price_unit), uom=uom, ref=self._cost_check_money(ref_line), src=source, hint=hint))
        elif abs(deviation) > tolerance:
            out.update(cost_check_state="warning", cost_check_message=_("Variación de %(dev)+.0f%% frente a %(ref)s (%(src)s); la tolerancia del producto es %(tol)s%%.",
                                                                        dev=deviation, ref=self._cost_check_money(ref_line), src=source, tol="%g" % tolerance))
        else:
            out.update(cost_check_state="ok", cost_check_message=False)
        return out

    @staticmethod
    def _cost_check_looks_like_unit(ratio):
        """A deviation that is a packing multiple (box of 10, dozen, 100, 1000 g in a kilo) points to the quantity or
        the unit of measure, not to the price."""
        big = ratio if ratio >= 1 else 1.0 / ratio
        return any(abs(big / f - 1.0) <= 0.15 for f in (6, 10, 12, 20, 24, 25, 50, 100, 500, 1000))

    def _cost_check_money(self, amount):
        return formatLang(self.env, amount, currency_obj=self.currency_id or self.env.company.currency_id)

    # --- subtle alert while typing ----------------------------------------------------
    @api.onchange("price_unit", "product_qty", "product_uom_id")
    def _onchange_cost_check_notify(self):
        """A toast, not a blocking dialog: the field also turns red or yellow in the line."""
        if not self.product_id or self.product_id.type != "consu":
            return
        try:
            self._compute_cost_check()
        except Exception:  # noqa: BLE001
            return None
        if self.cost_check_state == "danger":
            return {"warning": {"title": _("Revisa el costo de %s", self.product_id.display_name), "message": self.cost_check_message, "type": "notification"}}
        return None
