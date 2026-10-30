# -*- coding: utf-8 -*-
"""19.0.1.3.0: el PDF de la factura tambien va como adjunto del chatter
(DECISIONS.md #67, en la v17 fue la migracion 17.0.1.7.0).

Las solicitudes nuevas lo hacen al crearse (``_spr_post_pdf``). Aqui se agrega
a las que ya existen, sin mensaje nuevo en el chatter para no llenarlo con
avisos de hoy: solo se crea el adjunto en la solicitud y se fija como
``message_main_attachment_id``, como la migracion 17.0.1.7.0 de la v17. Si el
archivo no esta en el filestore se salta esa solicitud.

Ademas el reporte QWeb del instructivo (DECISIONS.md #69, port de la v17 #52)
se enlaza a la plantilla del correo, que es ``noupdate``: en bases que ya la
tienen la actualizacion del modulo no le agrega el reporte. Se agrega aqui sin
tocar el texto, que contabilidad pudo haber editado.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _attach_instructions_report(env):
    template = env.ref(
        "supplier_invoice_portal.mail_template_spr_instructions", raise_if_not_found=False)
    report = env.ref(
        "supplier_invoice_portal.report_spr_instructions", raise_if_not_found=False)
    if template and report and report not in template.report_template_ids:
        template.report_template_ids = [(4, report.id)]
        _logger.info("[SPR] 19.0.1.3.0: reporte del instructivo enlazado a la plantilla")


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _attach_instructions_report(env)
    Attachment = env["ir.attachment"]
    requests = env["supplier.payment.request"].with_context(
        active_test=False, bin_size=False
    ).search([("pdf_file", "!=", False), ("message_main_attachment_id", "=", False)])
    done = 0
    for request in requests:
        try:
            content = request.pdf_file
        except Exception:  # noqa: BLE001 - filestore incompleto en bases de prueba
            content = False
        if not content:
            continue
        attachment = Attachment.create({
            "name": request.pdf_filename or "%s.pdf" % request.name.replace("/", "_"),
            "datas": content,
            "mimetype": "application/pdf",
            "res_model": request._name,
            "res_id": request.id,
        })
        request.with_context(tracking_disable=True).message_main_attachment_id = attachment
        done += 1
    _logger.info("[SPR] 19.0.1.3.0: PDF adjunto: %d de %d solicitudes",
                 done, len(requests))
