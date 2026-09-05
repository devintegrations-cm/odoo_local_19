from odoo import fields, models, api

class PurchaseOrderReceipts(models.Model):
    _inherit = 'purchase.order'

    notify_requester_ids = fields.Many2many(
        comodel_name='res.partner',
        string='Notificar pago a',
        domain="[('type', '=', 'contact')]",
        help="Colocar los contactos diferentes al proveedor que deben ser notificados por correo cuando se registre un pago relacionado con esta orden de compra."
    )

    email_notification = fields.Char(
        string='Correos a notificar pago',
        compute='_compute_email_notification',
        store=True,
        help="Correos electrónicos de los contactos a notificar."
    )

    @api.depends('notify_requester_ids.email')
    def _compute_email_notification(self):
        for order in self:
            order.email_notification = ', '.join(
                order.notify_requester_ids.mapped('email')
            )

    @api.onchange('notify_requester_ids')
    def _onchange_notify_requester_ids(self):
        """Actualiza el campo email_notification en el formulario al cambiar los contactos."""
        self.email_notification = ', '.join(
            self.notify_requester_ids.mapped('email')
        )
