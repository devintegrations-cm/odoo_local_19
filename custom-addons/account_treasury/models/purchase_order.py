from odoo import _, api, fields, models

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
        # Los contactos sin correo se omiten (igual que en 17): `mapped('email')`
        # devuelve False para ellos y el join fallaría con TypeError, también al
        # editar cualquier contacto usado en una orden.
        for order in self:
            order.email_notification = ', '.join(
                email for email in order.notify_requester_ids.mapped('email') if email
            )

    def _notify_requesters_without_email(self):
        return self.notify_requester_ids.filtered(lambda contact: not contact.email)

    @api.onchange('notify_requester_ids')
    def _onchange_notify_requester_ids(self):
        """Actualiza el campo email_notification en el formulario al cambiar los
        contactos y avisa de inmediato si alguno no tiene correo."""
        self.email_notification = ', '.join(
            email for email in self.notify_requester_ids.mapped('email') if email
        )
        without_email = self._notify_requesters_without_email()
        if without_email:
            return {'warning': {
                'title': _("Contacto sin correo electrónico"),
                'message': _(
                    "Estos contactos de «Notificar pago a» no tienen correo, así "
                    "que no recibirían el aviso de pago:\n\n%(contacts)s\n\n"
                    "Agregue el correo en el contacto o quítelo de la lista. La "
                    "orden no se podrá confirmar mientras tanto.",
                    contacts="\n".join(without_email.mapped('display_name')),
                ),
            }}

    def _confirmation_error_message(self):
        """No se confirma una orden cuyos contactos a notificar no tienen correo.

        Punto de extensión del core (`purchase.order.button_confirm`): se evalúa
        en toda confirmación, también la que viene del asistente de variación de
        precios (purchase_price_validation).
        """
        error = super()._confirmation_error_message()
        if error:
            return error
        without_email = self._notify_requesters_without_email()
        if without_email:
            return _(
                "No se puede confirmar la orden %(order)s: estos contactos de "
                "«Notificar pago a» no tienen correo electrónico:\n\n%(contacts)s\n\n"
                "Agregue el correo en cada contacto o quítelos de la lista.",
                order=self.name,
                contacts="\n".join(without_email.mapped('display_name')),
            )
        return False
