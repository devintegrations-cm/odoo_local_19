import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Same name, label and default as purchase_price_validation: if both are installed they share the value, and this
    # module works without the other one (whose own checks block orders and receipts when they are switched on).
    porcent_variation = fields.Float(string="Variación de Costo", default=10.0,
                                     help="Margen permitido, en %, entre el precio de compra y el costo del producto. Fuera de este margen la línea se pone en amarillo.")

    cost_edit_warning = fields.Char(string="Aviso de cambio de costo", compute="_compute_cost_edit_warning",
                                    help="Aparece mientras se edita el costo si el cambio es incoherente frente al costo que tenía.")

    @api.depends("standard_price")
    def _compute_cost_edit_warning(self):
        for template in self:
            message = False
            try:
                origin = template._origin
                if origin and origin.id:
                    message = self.env["product.product"]._cost_edit_message(origin.standard_price, template.standard_price)
            except Exception:  # noqa: BLE001 - opening a product must never fail because of the check
                _logger.warning("Cost edit warning of product template %s failed", template.id, exc_info=True)
            template.cost_edit_warning = message

    @api.onchange("standard_price")
    def _onchange_standard_price_cost_check(self):
        """A toast while typing; the banner in the form says the same and nothing stops the save."""
        try:
            self._compute_cost_edit_warning()
            if self.cost_edit_warning:
                return {"warning": {"title": "Revisa el costo", "message": self.cost_edit_warning, "type": "notification"}}
        except Exception:  # noqa: BLE001
            return None
        return None
