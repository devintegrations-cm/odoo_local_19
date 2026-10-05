# -*- coding: utf-8 -*-
"""Datos de facturacion y documentos del proveedor en "Edit information" (/my/account).

Extiende el formulario estandar del portal (DECISIONS.md #44) para los
proveedores habilitados en el portal de facturas:

- Campos de facturacion electronica de Jorels (``l10n_co_edi_jorels``), solo si
  existen en ``res.partner``. El modulo no depende de Jorels: sin el, el
  formulario no los muestra.
- Camara de comercio, RUT y certificacion de cuenta bancaria.

En Odoo 19 el formulario se envia por JS a POST /my/address/submit y la
respuesta es JSON (``redirectUrl`` si salio bien, ``invalid_fields`` +
``messages`` si no). La validacion entra por ``_validate_address_values`` y lo
nuestro se escribe en ``_handle_extra_form_data``, despues de que Odoo escribe
el contacto del usuario.

Todo se escribe con sudo en el contacto comercial del usuario conectado; ningun
id de contacto viene del formulario. El resto del formulario (nombre, NIT,
direccion) sigue el camino estandar de Odoo, con su bloqueo ``can_edit_vat``.
"""


from markupsafe import Markup

from odoo import _, http, tools
from odoo.fields import Command
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

from ..models.res_partner_documents import SPR_DOCUMENTS
from ..services import pdf_check

# Solo PDF liviano y sin contrasena (DECISIONS.md #47): se previsualiza en el
# portal y en la ficha del contacto.
MAX_DOC_BYTES = pdf_check.MAX_PDF_BYTES
DOC_ACCEPT = ".pdf,application/pdf"

# (campo de res.partner, etiqueta). Son de l10n_co_edi_jorels; si no esta
# instalado, los campos no existen y no se muestran.
JORELS_FIELDS = [
    ("type_regime_id", "Tipo de regimen"),
    ("type_liability_id", "Tipo de responsabilidad"),
    ("municipality_id", "Municipio"),
    ("email_edi", "Email de facturacion"),
]


class SupplierAccountPortal(CustomerPortal):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _spr_account_partner(self):
        """Contacto comercial (sudo) cuyos datos edita el usuario, o vacio.

        Solo para proveedores habilitados en el portal de facturas: a los demas
        usuarios portal (clientes) el formulario no les cambia.
        """
        partner = request.env.user.partner_id.commercial_partner_id.sudo()
        if not partner.portal_invoice_enabled:
            return request.env["res.partner"]
        return partner

    def _spr_jorels_fields(self):
        """[(nombre, etiqueta, campo)] de los campos de Jorels que existen."""
        partner_fields = request.env["res.partner"]._fields
        result = []
        for name, label in JORELS_FIELDS:
            field = partner_fields.get(name)
            if field is not None and field.type in ("many2one", "many2many", "char"):
                result.append((name, label, field))
        return result

    @staticmethod
    def _spr_posted_ids(name):
        """Ids enviados en un select (varios si es many2many), sin vacios."""
        return [value for value in request.httprequest.form.getlist(name) if value]

    @staticmethod
    def _spr_upload(name):
        """El archivo subido en ``name`` o None si no se adjunto nada."""
        upload = request.httprequest.files.get(name)
        if upload is None or not getattr(upload, "filename", ""):
            return None
        return upload

    # ------------------------------------------------------------------
    # Validacion (19: corre en POST /my/address/submit, antes de escribir)
    # ------------------------------------------------------------------

    def _validate_address_values(self, address_values, partner_sudo, address_type,
                                 use_delivery_as_billing, required_fields, **kwargs):
        """Suma lo de este modulo a la validacion estandar de la direccion.

        Si algo falla se agrega a ``error_messages`` y la ruta responde JSON con
        ``invalid_fields`` + ``messages``; address.js resalta los campos y
        muestra los mensajes en el <div id="errors">.
        """
        invalid_fields, missing_fields, error_messages = super()._validate_address_values(
            address_values, partner_sudo, address_type, use_delivery_as_billing,
            required_fields, **kwargs,
        )
        if self._spr_account_partner():
            self._spr_validate_billing(invalid_fields, error_messages)
            self._spr_validate_documents(invalid_fields, error_messages)
        return invalid_fields, missing_fields, error_messages

    def _spr_validate_billing(self, invalid_fields, error_messages):
        form = request.httprequest.form
        # Los datos de facturacion electronica son obligatorios para el
        # proveedor habilitado, igual que los documentos (DECISIONS.md #53): un
        # campo que no llega cuenta como vacio, para que no se salte quitandolo
        # del formulario.
        for name, label, field in self._spr_jorels_fields():
            if field.type == "char":
                value = (form.get(name) or "").strip()
                if not value:
                    invalid_fields.add(name)
                    error_messages.append(_("%s: es obligatorio.") % label)
                elif name == "email_edi" and not tools.single_email_re.match(value):
                    invalid_fields.add(name)
                    error_messages.append(_("%s: el correo no es valido.") % label)
                continue
            raw_ids = self._spr_posted_ids(name)
            valid = all(value.isdigit() for value in raw_ids)
            if valid and raw_ids:
                ids = {int(value) for value in raw_ids}
                found = request.env[field.comodel_name].sudo().browse(ids).exists()
                valid = len(found) == len(ids) and (field.type == "many2many" or len(ids) == 1)
            if not raw_ids:
                invalid_fields.add(name)
                error_messages.append(_("%s: es obligatorio.") % label)
            elif not valid:
                invalid_fields.add(name)
                error_messages.append(_("%s: elija una opcion de la lista.") % label)

    def _spr_validate_documents(self, invalid_fields, error_messages):
        for name, label in SPR_DOCUMENTS:
            upload = self._spr_upload(name)
            if upload is None:
                continue
            content = upload.read()
            upload.seek(0)
            problem = (
                "el PDF supera %s MB" % (MAX_DOC_BYTES // (1024 * 1024))
                if len(content) > MAX_DOC_BYTES else pdf_check.pdf_problem(content)
            )
            if problem:
                invalid_fields.add(name)
                error_messages.append(_("%s: %s.") % (label, problem))

    # ------------------------------------------------------------------
    # Escritura (19: corre despues de que Odoo escribe el contacto)
    # ------------------------------------------------------------------

    def _handle_extra_form_data(self, extra_form_data, address_values):
        """Saca del formulario lo de este modulo y lo escribe en el comercial.

        Estos campos no estan en ``_get_frontend_writable_fields``: Odoo los
        ignora y quedan en ``extra_form_data``. Se leen del form (asi llegan
        tambien los vacios, que sirven para limpiar) y se escriben con sudo en
        el contacto comercial del usuario conectado.
        """
        super()._handle_extra_form_data(extra_form_data, address_values)
        commercial = self._spr_account_partner()
        if not commercial:
            return
        form = request.httprequest.form
        vals, changes = {}, []
        for name, label, field in self._spr_jorels_fields():
            if name not in form:
                continue
            if field.type == "char":
                new = (form.get(name) or "").strip()
                if new != (commercial[name] or ""):
                    vals[name] = new or False
                    changes.append(label)
                continue
            ids = [int(value) for value in self._spr_posted_ids(name)]
            if field.type == "many2one":
                new_id = ids[0] if ids else False
                if new_id != commercial[name].id:
                    vals[name] = new_id
                    changes.append(label)
            elif set(ids) != set(commercial[name].ids):
                vals[name] = [Command.set(ids)]
                changes.append(label)
        if vals:
            commercial.write(vals)
        # Cada documento queda como adjunto del contacto, visible en el
        # chatter, y el campo apunta a el (DECISIONS.md #48).
        attachments = request.env["ir.attachment"]
        for name, label in SPR_DOCUMENTS:
            upload = self._spr_upload(name)
            if upload is None:
                continue
            filename = upload.filename.replace("\\", "/").rsplit("/", 1)[-1]
            attachments |= commercial._spr_attach_document(name, filename, upload.read())
            changes.append("%s (%s)" % (label, filename))
        if changes:
            self._spr_log_changes(commercial, changes, attachments)

    def _spr_log_changes(self, commercial, changes, attachments=None):
        """Nota en el chatter del comercial: quien cambio que, desde el portal."""
        author = request.env.user.partner_id
        items = Markup("").join(Markup("<li>%s</li>") % change for change in changes)
        body = Markup("<p>%s</p><ul>%s</ul>") % (
            _("%s actualizo desde el portal:") % author.name, items)
        message = commercial.message_post(
            body=body, author_id=author.id, subtype_xmlid="mail.mt_note",
        )
        if attachments:
            # message_post solo enlaza adjuntos recien subidos con el mensaje; estos
            # ya son del contacto, asi que se enlazan a mano para verlos en la nota.
            message.sudo().attachment_ids = [Command.link(att.id) for att in attachments]

    # ------------------------------------------------------------------
    # Previsualizacion
    # ------------------------------------------------------------------

    @http.route(["/my/account/document/<string:field_name>"], type="http", auth="user",
                website=True)
    def spr_account_document(self, field_name, **kwargs):
        """El documento del proveedor conectado, para verlo en el navegador.

        Solo los tres campos de SPR_DOCUMENTS y solo del contacto comercial del
        usuario: no hay id en la URL, asi que no se puede pedir el de otro.
        """
        commercial = self._spr_account_partner()
        if not commercial or field_name not in dict(SPR_DOCUMENTS):
            raise request.not_found()
        attachment = commercial[field_name + "_id"].sudo()
        if not attachment:
            raise request.not_found()
        content = attachment.raw
        filename = attachment.name or "%s.pdf" % field_name
        return request.make_response(content, headers=[
            ("Content-Type", "application/pdf"),
            ("Content-Disposition", http.content_disposition(filename, disposition_type="inline")),
            ("X-Content-Type-Options", "nosniff"),
        ])

    # ------------------------------------------------------------------
    # Pagina
    # ------------------------------------------------------------------

    @http.route()
    def account(self, **post):
        # Sin redirect fijo: el core usa su default '/my' y con eso la plantilla
        # renderiza el hidden input ``callback`` (si se pasa redirect=None el
        # default se anula y el envio redirige a '/my/addresses').
        response = super().account(**post)
        qcontext = getattr(response, "qcontext", None)
        if qcontext is None:
            return response
        # Los errores del envio no pasan por aqui: la respuesta es JSON y
        # address.js marca los campos (is-invalid) y escribe en #errors.
        qcontext.update(self._spr_account_values())
        return response

    def _spr_account_values(self):
        """Valores de la plantilla: siempre definidos, aunque no sea proveedor."""
        commercial = self._spr_account_partner()
        jorels = []
        documents = []
        if commercial:
            for name, label, field in self._spr_jorels_fields():
                item = {"name": name, "label": label, "type": field.type}
                if field.type == "char":
                    item["value"] = commercial[name] or ""
                else:
                    options = request.env[field.comodel_name].sudo().search([])
                    item["options"] = [
                        (option.id, option.display_name)
                        for option in options.sorted(lambda option: option.display_name or "")
                    ]
                    item["selected"] = set(commercial[name].ids)
                jorels.append(item)
            for name, label in SPR_DOCUMENTS:
                documents.append({
                    "name": name,
                    "label": label,
                    "filename": commercial[name + "_id"].name or "",
                })
        return {
            "spr_account_partner": commercial,
            "spr_jorels_fields": jorels,
            "spr_documents": documents,
            "spr_doc_accept": DOC_ACCEPT,
            "spr_doc_max_mb": MAX_DOC_BYTES // (1024 * 1024),
        }