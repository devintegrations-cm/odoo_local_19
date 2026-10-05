# -*- coding: utf-8 -*-
import base64
import logging
import os

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import file_open

from ..services import dian_xml_parser

_logger = logging.getLogger(__name__)

# Guia del proveedor que se adjunta al instructivo (DECISIONS.md #61). Ruta
# relativa al addon: file_open la resuelve contra los addons_path, asi que el
# PDF se lee en cada clic y se puede reemplazar sin tocar datos ni version.
SPR_INSTRUCTIONS_PDF = (
    "supplier_invoice_portal/static/doc/guia/"
    "Instructivo_portal_proveedores_Libertario.pdf"
)


class ResPartner(models.Model):
    _inherit = "res.partner"

    portal_invoice_enabled = fields.Boolean(
        string="Puede radicar facturas en el portal",
        default=False,
        help="Habilita a este proveedor para enviar solicitudes de pago desde el portal. "
             "Se marca en la empresa (o en la persona natural sin contacto padre): sus "
             "contactos hijos con usuario de portal radican a nombre de ella.",
    )
    spr_support_document = fields.Boolean(
        string="No obligado a facturar (documento soporte)",
        default=False,
        help="El proveedor no expide factura electronica: radica una cuenta de cobro y "
             "la compania emite el documento soporte al registrarla.",
    )
    spr_request_ids = fields.One2many(
        "supplier.payment.request", "partner_id", string="Solicitudes de pago"
    )
    spr_request_count = fields.Integer(
        string="Numero de solicitudes", compute="_compute_spr_request_count"
    )

    @api.depends("spr_request_ids")
    def _compute_spr_request_count(self):
        grouped = self.env["supplier.payment.request"]._read_group(
            [("partner_id", "in", self.ids)],
            groupby=["partner_id"],
            aggregates=["__count"],
        )
        counts = {partner.id: count for partner, count in grouped}
        for partner in self:
            partner.spr_request_count = counts.get(partner.id, 0)

    @api.constrains("portal_invoice_enabled", "vat", "parent_id", "is_company")
    def _check_portal_invoice_enabled(self):
        """Requisitos para habilitar a un proveedor en el portal (DECISIONS.md #37).

        1. Se habilita el contacto comercial, no un contacto hijo: el portal lee
           el indicador de ``commercial_partner_id``, en el hijo no tendria efecto.
        2. Tiene NIT: sin el no se puede verificar el emisor de sus facturas.

        Un NIT repetido en otro tercero no bloquea (antes si, DECISIONS.md #37):
        quien radica es el usuario portal que se le crea al proveedor, y ese
        usuario solo ve las ordenes del tercero al que pertenece.
        """
        for partner in self.filtered("portal_invoice_enabled"):
            if partner.commercial_partner_id != partner:
                raise ValidationError(_(
                    "%s es un contacto de %s. Habilite el portal en %s: sus contactos "
                    "radican a nombre de ella."
                ) % (partner.name, partner.commercial_partner_id.name,
                     partner.commercial_partner_id.name))
            if not dian_xml_parser.normalize_nit(partner.vat):
                raise ValidationError(_(
                    "Registre el NIT de %s antes de habilitarlo en el portal de facturas."
                ) % partner.name)

    def action_view_spr_requests(self):
        self.ensure_one()
        partner = self.commercial_partner_id
        return {
            "type": "ir.actions.act_window",
            "name": "Solicitudes de pago",
            "res_model": "supplier.payment.request",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", partner.id)],
            "context": {"default_partner_id": partner.id},
        }

    def _spr_instructions_attachment(self):
        """Adjunto reutilizable con la guia en PDF, o ``None`` (DECISIONS.md #61).

        El PDF se materializa como ``ir.attachment`` en el servidor y al
        asistente solo se le pasa su id: el comando ``(0, 0, {...})`` con el
        contenido en base64 puesto en el contexto no sobrevive al formulario
        del cliente en 19 y el ``create`` del asistente revienta con un
        NotNullViolation en ``ir.attachment.name``. Es ademas el patron del
        core: ``mail.compose.message._compute_attachment_ids`` crea el
        adjunto con ``ir.attachment.create`` y entrega ids, nunca datas en
        un default de contexto.

        Se crea una sola vez y se reutiliza en cada clic (mismo
        ``res_model``/``res_id``/``name``); si el PDF cambia en disco, se
        actualiza al detectar otro checksum. Si el archivo no esta (un
        copiado del modulo sin ``static/doc``), devuelve ``None``: el correo
        se abre igual sin adjunto y se avisa en el log, el texto del
        instructivo se sostiene por si solo.
        """
        try:
            with file_open(SPR_INSTRUCTIONS_PDF, "rb") as pdf:
                raw = pdf.read()
        except FileNotFoundError:
            _logger.warning(
                "No se encontro %s: el instructivo se abre sin la guia adjunta.",
                SPR_INSTRUCTIONS_PDF,
            )
            return None
        attachment_model = self.env["ir.attachment"]
        name = os.path.basename(SPR_INSTRUCTIONS_PDF)
        # Mismo "estacionamiento" que usa el core para los adjuntos que nacen
        # en el asistente (res_id 0): no aparece en ningun chatter y no queda
        # ligado al proveedor si compras cancela.
        attachment = attachment_model.search([
            ("res_model", "=", "mail.compose.message"),
            ("res_id", "=", 0),
            ("name", "=", name),
        ], limit=1)
        vals = {
            "name": name,
            "datas": base64.b64encode(raw),
            "type": "binary",
            "res_model": "mail.compose.message",
            "res_id": 0,
        }
        if not attachment:
            return attachment_model.create(vals)
        if attachment.checksum != attachment_model._compute_checksum(raw):
            attachment.write(vals)
        return attachment

    def _spr_instructions_pdf_commands(self):
        """Comando de enlace al adjunto con la guia, o ``[]``.

        Al asistente llega solo el id (``(4, id)``): el cliente maneja un
        entero y el PDF nunca cruza el formulario. Ver
        ``_spr_instructions_attachment`` para la creacion y la reutilizacion.
        """
        attachment = self._spr_instructions_attachment()
        return [(4, attachment.id)] if attachment else []

    def action_spr_send_instructions(self):
        """Abre el correo con el instructivo del portal para el proveedor.

        Se abre el asistente en vez de enviar directo para que compras revise
        los destinatarios; la guia en PDF viene adjunta (DECISIONS.md #61).
        """
        self.ensure_one()
        if not self.portal_invoice_enabled:
            raise UserError(_("Habilite primero el portal de facturas para %s.") % self.name)
        template = self.env.ref("supplier_invoice_portal.mail_template_spr_instructions")
        return {
            "type": "ir.actions.act_window",
            "name": _("Enviar instructivo del portal"),
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_model": "res.partner",
                "default_res_ids": self.ids,
                "default_template_id": template.id,
                "default_composition_mode": "comment",
                "default_email_layout_xmlid": "mail.mail_notification_light",
                "default_attachment_ids": self._spr_instructions_pdf_commands(),
            },
        }

    def _spr_cutoff_label(self):
        """Texto del corte de radicacion para el instructivo, p. ej. '12:00 m.'."""
        hour = self.env["supplier.payment.request"]._cutoff_settings()[1]
        hours, minutes = int(hour), int(round((hour - int(hour)) * 60))
        suffix = "m." if (hours, minutes) == (12, 0) else ("p. m." if hours >= 12 else "a. m.")
        return "%d:%02d %s" % (hours if hours <= 12 else hours - 12, minutes, suffix)
