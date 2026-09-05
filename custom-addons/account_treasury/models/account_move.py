import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    buyers_invoice_ids = fields.Many2many(
        'res.users',
        string='Solicitantes de Compra', 
        readonly=True,
        compute='_compute_responsible_user_id', 
        help='List of user that create the related order purchase'
    )

                
    @api.depends('invoice_line_ids.purchase_order_id.user_id')
    def _compute_responsible_user_id(self):
        for move in self:
            buyers_ids = {}
            for line in move.invoice_line_ids:
                if line.purchase_order_id.user_id:
                    buyer_id = line.purchase_order_id.user_id
                    buyers_ids[buyer_id.id] = buyer_id
            move.buyers_invoice_ids = [(6, 0, [buyer.id for buyer in buyers_ids.values()])]
            
    def _get_related_purchase_order(self):
        self.ensure_one()
        po_ids = []
        for line in self.invoice_line_ids:
            if line.purchase_line_id and line.purchase_line_id.order_id:
                po_ids.append(line.purchase_line_id.order_id)
        if False:
            po_ids = list(set(po_ids))  # eliminar duplicados
            po_ids = self.env['purchase.order'].search(po_ids)
        return po_ids