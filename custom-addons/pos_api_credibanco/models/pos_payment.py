import json

from odoo import api, fields, models

from .pos_payment_credibanco import APPROVAL_CODE_POSITION, TRANSACTION_ID_POSITION


class PosPayment(models.Model):
    _inherit = "pos.payment"

    credibanco_extra_info = fields.One2many(
        "pos.payment.credibanco",
        "payment_order_id",
        string="Información Terminal de pago",
        readonly=True,
    )
    credibanco_approval_number = fields.Char(
        string="Número de aprobación",
        copy=False,
        index=True,
        help="Approval code returned by the Credibanco terminal. Stored here "
             "because it is the number the cashier is asked for when calling the "
             "acquirer.",
    )
    credibanco_pending_sale = fields.Char(
        string="Venta pendiente en el datáfono",
        copy=False,
        help="Protocol positions of the sale that was sent without a confirmed "
             "answer, as a JSON object. Recovery and cancellation read it as it "
             "was sent: recomputing the references from the session could point "
             "the terminal at somebody else's transaction.",
    )
    credibanco_cash_register = fields.Char(
        string="Cajera enviada (42)",
        copy=False,
        readonly=True,
        help="Exact value sent to the terminal in message position 42. Kept "
             "because the cancellation must echo what was sent, not a value "
             "derived again from the session and the cashier.",
    )
    credibanco_number_transaction = fields.Char(
        string="Transacción enviada (53)",
        copy=False,
        readonly=True,
        help="Exact transaction number sent in message position 53. It must be "
             "unique per order and per payment, and it is never truncated.",
    )
    credibanco_operator = fields.Char(
        string="Operador enviado (83)",
        copy=False,
        readonly=True,
        help="Cashier representation actually sent in message position 83. The "
             "employee keeps its full name in hr.employee; only this wire "
             "representation is limited to the protocol length.",
    )
    credibanco_response = fields.Char(
        string="Respuesta del datáfono",
        copy=False,
        help="Raw answer of the terminal, as a JSON object of protocol positions. "
             "Kept for auditability: it is also what feeds the readable breakdown.",
    )
    credibanco_anulation_of = fields.Char(
        string="Anulación de (línea anulada)",
        copy=False,
        readonly=True,
        help="uuid of the payment line this one annuls.  Odoo 17 registered an "
             "anulación as a negative payment line so accounting and the "
             "acquirer settlement see the sale and its reversal as two "
             "movements.  Odoo 19's native reversal would leave the sale's "
             "amount at 0 (nothing to reconcile), so the anulación is "
             "represented as a compensating negative line.  This field is "
             "the marker that blocks the line from being deleted: the "
             "terminal already reversed the money, and removing the line "
             "would undo the accounting while the bank keeps the reversal.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Materialise the terminal answer when a payment arrives with one.

        The interface writes the answer on the local payment line, and Odoo 19
        synchronises it as plain field values with the order: there is no
        ``export_as_JSON`` hook to override anymore, and unknown keys in the
        payload would be rejected.  Turning the raw answer into readable rows
        therefore happens here, once, for every path that creates a payment.
        """
        payments = super().create(vals_list)
        for payment, vals in zip(payments, vals_list):
            if vals.get("credibanco_response"):
                payment._credibanco_process_response(vals["credibanco_response"])
        return payments

    def _credibanco_process_response(self, raw_response):
        """Parse the stored answer into breakdown rows and mirror the approval."""
        self.ensure_one()
        try:
            answer = json.loads(raw_response)
        except (TypeError, ValueError):
            # A malformed answer must not lose the payment: keep the raw value
            # and let a manager complete the information from the form view.
            return False

        if not isinstance(answer, dict):
            return False

        rows = self.env["pos.payment.credibanco"]._rows_from_answer(answer)
        values = {"credibanco_extra_info": rows}

        approval = answer.get(APPROVAL_CODE_POSITION)
        if approval and not self.credibanco_approval_number:
            values["credibanco_approval_number"] = str(approval)

        # Derived from the stored answer rather than trusted from the browser:
        # the acquirer reference is what support needs later, and a value that
        # only lived in the interface would be lost on a failed sync.
        transaction = answer.get(TRANSACTION_ID_POSITION)
        if transaction and not self.transaction_id:
            values["transaction_id"] = str(transaction)

        # pos_voucher_num shows the approval number in accounting views. It is an
        # optional module, so the field is only written when it exists: the link
        # between both modules is the value, not a dependency in the manifest.
        if approval and "voucher_num" in self._fields and not self.voucher_num:
            values["voucher_num"] = str(approval)

        self.write(values)
        return True

    def open_credibanco_extra_info_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Agregar Información Manual",
            "res_model": "credibanco.extra.info.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("pos_api_credibanco.view_credibanco_extra_info_wizard").id,
            "target": "new",
            "context": {"default_payment_order_id": self.id},
        }
