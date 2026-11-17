"""Read-only trail of the purchase orders that earlier versions of this module booked from Clara transactions.

Nothing here creates, confirms or writes a purchase order any more: the fields stay so the orders already
booked keep their Clara data (the "Clara" tab of the order form and the "Desde Clara" filter). The link that
the dashboard uses today is computed on the Clara transaction, from the order code the legalization bot
writes in the Clara comment (see clara_connector).
"""
from odoo import api, fields, models

CLARA_DECISIONS = [
    ("approve", "Aprobada"),
    ("review", "En revisión"),
    ("reject", "Rechazada"),
]


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    clara_transaction_uuid = fields.Char(string="Transacción Clara", copy=False, index=True, readonly=True,
                                         help="Identificador de la transacción de tarjeta corporativa en Clara (órdenes registradas por versiones anteriores).")
    clara_transaction_date = fields.Date(string="Fecha transacción Clara", copy=False, readonly=True)
    clara_cardholder = fields.Char(string="Titular de la tarjeta", copy=False, readonly=True)
    clara_cardholder_uuid = fields.Char(string="Uuid del titular en Clara", copy=False, readonly=True, index=True)
    clara_cardholder_email = fields.Char(string="Correo del titular", copy=False, readonly=True)
    clara_card_last4 = fields.Char(string="Tarjeta (últimos 4)", size=4, copy=False, readonly=True)
    clara_merchant = fields.Char(string="Comercio", copy=False, readonly=True)
    clara_amount = fields.Monetary(string="Cobro de la tarjeta", copy=False, readonly=True, currency_field="currency_id",
                                   help="Valor cobrado por la tarjeta en Clara, en la moneda de la orden.")
    clara_description = fields.Text(string="Descripción en Clara", copy=False, readonly=True,
                                    help="Lo que el titular escribió en la transacción de Clara cuando se registró la orden.")
    clara_decision = fields.Selection(CLARA_DECISIONS, string="Decisión registrada", copy=False, readonly=True, index=True)
    clara_decision_reason = fields.Text(string="Motivo de la decisión", copy=False, readonly=True)
    clara_analytic_rule_id = fields.Many2one("clara.analytic.rule", string="Regla de analítico", copy=False, readonly=True,
                                             help="Regla (titular o área) que fijó la cuenta analítica de esta orden.")
    clara_receipt_count = fields.Integer(string="Comprobantes", compute="_compute_clara_receipt_count")

    @api.depends("clara_transaction_uuid")
    def _compute_clara_receipt_count(self):
        counts = dict(self.env["ir.attachment"]._read_group(
            [("res_model", "=", "purchase.order"), ("res_id", "in", self.ids), ("clara_receipt", "=", True)], ["res_id"], ["__count"]))
        for order in self:
            order.clara_receipt_count = counts.get(order.id, 0)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    clara_receipt = fields.Boolean(string="Comprobante Clara", default=False, index=True,
                                   help="Comprobante traído desde Clara por una versión anterior del módulo.")
