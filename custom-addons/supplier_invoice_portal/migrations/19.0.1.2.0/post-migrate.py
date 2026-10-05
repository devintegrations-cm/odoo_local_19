# -*- coding: utf-8 -*-
"""19.0.1.2.0: reactiva las vistas del modulo que el upgrade haya desactivado.

Al pasar de 17 a 19, una vista heredada cuyo xpath o arch fallo durante la
actualizacion puede quedar con ``active = false``; la carga de datos del ``-u``
reescribe el arch pero no la vuelve a activar, y la funcionalidad desaparece
sin error (p. ej. el formulario de radicar o el boton de la orden de compra).
Aqui, ya con los arch de 19 cargados, se reactivan con el ORM: asi se valida
la vista combinada. Si alguna sigue rota, se deja inactiva y se avisa en el log
en vez de tumbar el upgrade o romper la pagina.

Excepcion: ``portal_my_home_spr`` es ``customize_show``: el sitio puede tenerla
apagada a proposito desde el editor y no se le cambia.

Idempotente: solo toca las vistas inactivas.

Ademas lleva el instructivo para el proveedor (``mail_template_spr_instructions``,
``noupdate``) a su texto de 19, con el paso de cargar los documentos antes de
radicar (DECISIONS.md #50). Solo si la plantilla sigue con el texto original de
17: una plantilla personalizada en produccion no se pisa. Se compara el texto
visible (sin etiquetas ni espacios), no el HTML, porque el sanitizador de 17 y
el de 19 pueden serializar distinto. Idempotente: con el texto nuevo ya no
coincide la huella de 17.
"""
import hashlib
import html
import logging
import os
import re

from lxml import etree

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

KEEP_AS_IS = ("portal_my_home_spr",)

# Huella del texto visible del body_html del instructivo de 17.0.1.2.0.
INSTRUCTIONS_17_FINGERPRINT = "ca9d771f25f53b2d1318e6bf5716d761934dd12fc6cb8e3b86d76f16941cdc7e"
INSTRUCTIONS_XMLID = "mail_template_spr_instructions"


def _fingerprint(body):
    text = re.sub(r"<[^>]+>", " ", body or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return hashlib.sha256(text.encode()).hexdigest()


def _module_instructions_body():
    """body_html del instructivo tal como lo carga el XML del modulo (convert.py)."""
    path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "mail_template_data.xml")
    root = etree.parse(path).getroot()
    node = root.xpath("//record[@id='%s']/field[@name='body_html']" % INSTRUCTIONS_XMLID)[0]
    return "".join(etree.tostring(child, method="html", encoding="unicode") for child in node)


def _update_instructions(env):
    template = env.ref("supplier_invoice_portal." + INSTRUCTIONS_XMLID, raise_if_not_found=False)
    if not template:
        return
    env.cr.execute("SELECT body_html FROM mail_template WHERE id = %s", [template.id])
    stored = env.cr.fetchone()[0] or {}
    if not stored or any(_fingerprint(body) != INSTRUCTIONS_17_FINGERPRINT
                         for body in stored.values()):
        _logger.info("supplier_invoice_portal 19.0.1.2.0: el instructivo no es el de 17 "
                     "(ya actualizado o personalizado): no se toca")
        return
    new_body = _module_instructions_body()
    for lang in sorted(stored, key=lambda code: code != "en_US"):
        template.with_context(lang=lang).write({"body_html": new_body})
    _logger.info("supplier_invoice_portal 19.0.1.2.0: instructivo actualizado (%s)",
                 ", ".join(sorted(stored)))


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _update_instructions(env)
    data = env["ir.model.data"].search([
        ("module", "=", "supplier_invoice_portal"),
        ("model", "=", "ir.ui.view"),
        ("name", "not in", KEEP_AS_IS),
    ])
    views = env["ir.ui.view"].with_context(active_test=False).browse(data.mapped("res_id"))
    for view in views.exists().filtered(lambda view: not view.active):
        try:
            with cr.savepoint():
                view.write({"active": True})
            _logger.info("supplier_invoice_portal 19.0.1.2.0: vista reactivada: %s (%s)",
                         view.name, view.id)
        except Exception as error:  # noqa: BLE001 - una vista rota no tumba el upgrade
            env.invalidate_all()  # el savepoint revirtio la base, no la cache
            _logger.warning(
                "supplier_invoice_portal 19.0.1.2.0: la vista %s (%s) sigue inactiva, "
                "no valida en 19: %s", view.name, view.id, error,
            )
