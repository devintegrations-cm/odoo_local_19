# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    spr_request_ids = fields.Many2many(
        "supplier.payment.request",
        "supplier_payment_request_purchase_rel",
        "purchase_id",
        "request_id",
        string="Solicitudes de pago",
        copy=False,
    )
    spr_request_count = fields.Integer(
        string="Numero de solicitudes", compute="_compute_spr_request_count"
    )

    @api.depends("spr_request_ids")
    def _compute_spr_request_count(self):
        for order in self:
            order.spr_request_count = len(order.spr_request_ids)

    def _spr_vendor_bills(self):
        """Facturas de proveedor (no anuladas, borrador incluido) ligadas a la orden.

        Una orden con factura ya no acepta otra factura ni cuenta de cobro por el
        portal: lo que falte o sobre se corrige con nota credito o debito sobre
        esa factura (DECISIONS.md #40).
        """
        return self.invoice_ids.filtered(
            lambda move: move.move_type == "in_invoice" and move.state != "cancel"
        )

    def _spr_open_requests(self):
        """Radicaciones de factura o cuenta de cobro en curso sobre la orden.

        Todas menos las rechazadas y canceladas: mientras contabilidad no crea la
        factura, la orden todavia no tiene factura y sin esto se podria radicar
        otra vez (DECISIONS.md #46). Las notas no cuentan: corrigen una factura.
        """
        return self.spr_request_ids.filtered(
            lambda req: req.document_type in ("invoice", "support_doc")
            and req.state not in ("rejected", "cancelled")
        )

    def _spr_accepts_invoice(self):
        """True si el proveedor puede radicar por el portal una factura de esta orden.

        Las mismas condiciones que el formulario usa para ofrecerla
        (``_spr_open_orders`` del controlador): proveedor habilitado, orden
        confirmada, no totalmente facturada y sin factura (DECISIONS.md #40).
        """
        self.ensure_one()
        return bool(
            self.partner_id.commercial_partner_id.portal_invoice_enabled
            and self.state == "purchase"  # en 19 no hay "done": la bloqueada sigue en purchase
            and self.invoice_status != "invoiced"
            and not self._spr_vendor_bills()
            and not self._spr_open_requests()
        )

    def action_view_spr_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Solicitudes de pago",
            "res_model": "supplier.payment.request",
            "view_mode": "list,form",
            "domain": [("purchase_ids", "in", self.id)],
            "context": {
                "default_purchase_ids": [(6, 0, self.ids)],
                "default_partner_id": self.partner_id.commercial_partner_id.id,
            },
        }
