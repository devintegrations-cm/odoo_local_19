import logging
import base64

from markupsafe import Markup

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    payment_image = fields.Binary(string="Payment Image", attachment=True)
    attachment_id = fields.Many2one('ir.attachment', string='Attachment', help='Attachment')
    file_binary = fields.Binary(string="TXT file")

    email_notification = fields.Boolean(string = 'Notificacion por correo', store=True, compute='_compute_email_notification')
    
    def send_partner_email(self):
        # solicitantes_cc = set()

        # invoices = self._get_reconciled_invoices()
        # for invoice in invoices:
        #     # facturas_pagadas.append(invoice)
        #     for user in invoice.buyers_invoice_ids:
        #         if user.email:
        #             solicitantes_cc.add(user.email)
                    
        
        
        emails_notify = set()
        motivos = []
        for payment in self:
            invoices = payment._get_reconciled_invoices()
            if not invoices:
                motivos.append("el pago no está aplicado a ninguna factura de proveedor")
                continue
            for invoice in invoices:
                po_ids = invoice._get_related_purchase_order()
                if not po_ids:
                    motivos.append(f"la factura {invoice.name} no proviene de una orden de compra")
                    _logger.warning("No se encontro orden de compra para la factura %s", invoice.name)
                    continue
                for po in po_ids:
                    if not po.notify_requester_ids:
                        motivos.append(f"la orden de compra {po.name} no tiene contactos en 'Notificar pago a'")
                        continue
                    sin_correo = po.notify_requester_ids.filtered(lambda c: not c.email)
                    if sin_correo:
                        motivos.append(
                            f"en la orden {po.name}, estos contactos no tienen correo: "
                            + ", ".join(sin_correo.mapped('name'))
                        )
                    for contact in po.notify_requester_ids:
                        if contact.email:
                            emails_notify.add(contact.email)

        # Sin esto, no encontrar destinatarios era indistinguible de haberlos
        # notificado: no se creaba ningun correo y no quedaba rastro en ningun lado.
        # Se deja la razon en el chatter del pago, que es donde mira el usuario.
        if not emails_notify:
            detalle = "; ".join(dict.fromkeys(motivos)) or "no se hallaron contactos a notificar"
            # Markup y no una cadena simple: desde Odoo 17 message_post escapa el
            # texto plano, asi que el HTML se veria con las etiquetas literales.
            self.message_post(
                body=Markup(
                    "<p>No se envió la notificación a los solicitantes: %s.</p>"
                    "<p>El aviso al proveedor sí se envió.</p>"
                ) % detalle,
                subtype_xmlid='mail.mt_note',
            )
            _logger.info("Sin destinatarios para la notificacion a solicitantes: %s", detalle)
        
        if emails_notify:
            email_values = {
                'email_to': ','.join(emails_notify)
            }
            template_id = self.env.ref('account_treasury.email_request_template_pay_not', raise_if_not_found=False)
            if not template_id:
                raise UserError('Plantilla de correo electrónico no encontrada.')        
            template_id.attachment_ids = [(6, 0, [])]
            template_id.send_mail(self.id, email_values=email_values, force_send=True)
                        
                        
        # Si el pago no esta aplicado a ninguna factura, el correo sale sin detalle.
        # En Odoo 19 esto puede pasar por dos motivos distintos y conviene poder
        # distinguirlos en el log:
        #  - el pago no tiene asiento contable (move_id vacio), que ocurre cuando la
        #    linea del metodo de pago no tiene cuenta de pagos pendientes configurada.
        #    En Odoo 17 era imposible: el asiento era obligatorio (required=True).
        #  - el pago tiene asiento pero no esta conciliado con ninguna factura, o sea
        #    es un pago suelto y no hay nada que listar.
        for payment in self:
            if not payment.reconciled_bill_ids:
                if not payment.move_id:
                    _logger.warning(
                        "Pago %s sin asiento contable: no se puede relacionar ninguna factura. "
                        "Revisar la cuenta de pagos pendientes en la linea del metodo de pago "
                        "'%s' del diario '%s'.",
                        payment.name, payment.payment_method_line_id.name,
                        payment.journal_id.display_name,
                    )
                else:
                    _logger.info(
                        "Pago %s sin facturas conciliadas: el correo sale sin detalle.",
                        payment.name,
                    )

        # Codigo original
        self.pwarning('SE ENVIO EMAIL EN: ',self.id)
        template_id = self.env.ref('account_treasury.email_template_pay_not', raise_if_not_found=False)
        if not template_id:
            raise UserError('Plantilla de correo electrónico no encontrada.')        
        template_id.attachment_ids = [(6, 0, [])]
        # template_id.send_mail(self.id, email_values=email_values, force_send=True)
        template_id.send_mail(self.id, force_send=True)
        self.email_notification = True


            
    def _get_reconciled_invoices(self):
        """Facturas de proveedor a las que se aplica este pago.

        En Odoo 17 esto se resolvia recorriendo las conciliaciones de los apuntes
        del asiento del pago, porque el asiento era obligatorio (move_id era
        required=True) y la conciliacion era el unico vinculo posible.

        En Odoo 19 eso ya no alcanza. account.payment tiene un campo invoice_ids
        nuevo que, en palabras del propio nucleo, "contains the invoice even if
        they don't have a journal entry and are not reconciled"
        (account/models/account_payment.py:139). Y reconciled_bill_ids combina ese
        enlace directo con lo que ademas se encuentre por conciliacion.

        Seguir recorriendo move_id.line_ids dejaba sin notificar a los solicitantes
        cada vez que el pago no tenia asiento contable, que en 19 es un caso real:
        el correo al proveedor SI listaba la factura -porque usa el campo del
        nucleo- mientras esta funcion devolvia vacio.
        """
        return self.reconciled_bill_ids
    
    

    @api.depends('name', 'amount')
    def _compute_email_notification(self):
        # Odoo 19: `mail.message.description` fue eliminado (existia en 17 como
        # "subject o inicio del cuerpo"). El equivalente es subject / preview.
        for pay in self:
            email_msg_id = [
                e for e in pay.message_ids
                if 'Notificación de Pago'.lower() in (e.subject or e.preview or '').lower()
                and e.message_type == 'email'
            ]
            pay.email_notification = len(email_msg_id) > 0

    def pwarning(self, key, val):
        _logger.warning(f'{key}: {val}')

    def send_payment_image(self):
        if not self.reconciled_bill_ids:
            raise UserError('Por favor asocie la (s) factura (s) al pago')
        if not self.payment_image:
            raise UserError('Por Favor adjunte un comprobante')
        template_id = self.env.ref('account_treasury.email_template_pay_not', raise_if_not_found=False)
        if not template_id:
            raise UserError('Plantilla de correo electrónico no encontrada.')
        
        attachment_vals = {
            'name': f'Payment {self.name}.png',
            'type': 'binary',
            'datas': self.payment_image,
            'res_model': self._name,
            'res_id': self.id,
        }
        attachment = self.env['ir.attachment'].create(attachment_vals)
        
        template_id.attachment_ids = [(6, 0, [attachment.id])]
        template_id.send_mail(self.id, force_send=True)        
        return True

    def create_txt_file(self):
        data = ""
        for rec in self:
            data += f'{rec.name} : {rec.amount} \n'
        self.attachment_id = self.env['ir.attachment'].create({
            'name': 'file.txt',
            'type': 'binary',
            'datas': base64.b64encode(data.encode()),
            #'res_id': self.id,
            'mimetype': 'text/plain'
        })

        # Preparar la URL de descarga
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        download_url = '/web/content/%s?download=true' % self.attachment_id.id

        # Construir y retornar la acción de URL
        return {
            "type": "ir.actions.act_url",
            "url": str(base_url) + str(download_url),
            "target": "new",
        }
