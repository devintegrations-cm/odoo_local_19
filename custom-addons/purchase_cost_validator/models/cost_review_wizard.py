from odoo import fields, models
from odoo.exceptions import AccessError


class PurchaseCostReviewWizard(models.TransientModel):
    _name = "purchase.cost.review.wizard"
    _description = "Recepción con desfase de costo"

    picking_ids = fields.Many2many("stock.picking", string="Recepciones")
    message = fields.Html(string="Detalle", readonly=True, sanitize=False)
    can_approve = fields.Boolean(readonly=True)

    def action_approve(self):
        self.ensure_one()
        if not self.picking_ids._cost_check_is_reviewer():
            raise AccessError("Solo el revisor de compras o un administrador de inventario puede aprobar esta recepción.")
        return self.picking_ids._cost_check_approve()

    def action_open_orders(self):
        self.ensure_one()
        orders = self.picking_ids.move_ids.purchase_line_id.order_id
        action = {"type": "ir.actions.act_window", "res_model": "purchase.order", "name": "Órdenes de compra"}
        if len(orders) == 1:
            return dict(action, res_id=orders.id, view_mode="form", views=[(False, "form")])
        return dict(action, domain=[("id", "in", orders.ids)], view_mode="list,form", views=[(False, "list"), (False, "form")])
