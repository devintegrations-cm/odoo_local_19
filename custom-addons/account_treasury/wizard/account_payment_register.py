import logging
import base64

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
"""TODO:
    Colocar validaciones: 
        + automaticamente se cargue info de la cuenta del proveedor en el pago
    """
class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    send_email = fields.Boolean(string='Enviar Notificación de pago', help="Set 'True' to send an email to the respective partner")
    
    @api.onchange('send_email')
    def up_send_email(self):
        for rec in self:
            rec.send_email = self.send_email  
            
    def print_attrs(self, obj):
        for attr in dir(self):
            if not attr.startswith('_'):
                valor = getattr(self, attr)
                _logger.warning(f'ATTR: {attr} \t VLR: {valor}')
                
    def _create_payments(self):
        self._validate_emails()
        payment_ids = super(AccountPaymentRegister, self)._create_payments()  
        if self.send_email:
            for payment in payment_ids:
                payment.send_partner_email()
        return payment_ids
        
    def _validate_emails(self):
        """
        Revisa si los contactos tienen un correo asociado
        """
        move_line_id = self.line_ids
        missing_emails = []
        for payment in move_line_id:
            if not payment.partner_id.email:
                missing_emails.append(payment.partner_id.name)
        missing_emails = sorted(set(missing_emails))
        missing_emails = ', '.join(missing_emails)
        if missing_emails:
            raise UserError(f'Contactos in correo electrónico: {missing_emails}')

