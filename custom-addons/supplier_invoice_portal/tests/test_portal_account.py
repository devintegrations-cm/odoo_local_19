# -*- coding: utf-8 -*-
"""Tests de "Edit information" (/my/account) del proveedor (DECISIONS.md #44).

Documentos (camara de comercio, RUT, certificacion bancaria) y campos de
facturacion electronica de Jorels. La base de pruebas no tiene Jorels: se
comprueba que sus campos no aparecen ni rompen nada, y el camino generico
(select, select multiple, texto) se prueba cambiando la lista de campos por
campos estandar de res.partner.
"""

import base64
import json
import re
from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from ..controllers import portal_account
from .common import SprCase

INPUT_RE = re.compile(r"<input\b[^>]*>")
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')

PDF = b"%PDF-1.4\n%dummy\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
# Un PDF cifrado declara /Encrypt en el trailer (DECISIONS.md #47).
ENCRYPTED_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<</Root 1 0 R/Encrypt 2 0 R>>\n%%EOF\n"


@tagged("post_install", "-at_install")
class TestPortalAccount(SprCase, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country = cls.env.ref("base.co")
        # NIT con DV valido: con base_vat (Jorels lo trae) y pais Colombia se
        # verifica el digito, y el de common.py no lo es.
        cls.supplier.vat = "900123456-8"
        cls.contact = cls.env["res.partner"].create({
            "name": "Ana Contadora",
            "parent_id": cls.supplier.id,
            "email": "ana@cafesdelsur.example",
            "phone": "3001234567",
            "street": "Calle 1 # 2-3",
            "city": "Pitalito",
            "zip": "190001",
            "country_id": cls.country.id,
            "company_id": False,
        })
        cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Ana Contadora",
            "login": "ana_account",
            "password": "ana_account_pw_2026",
            "partner_id": cls.contact.id,
            "company_id": cls.company.id,
            "company_ids": [(6, 0, cls.company.ids)],
            "group_ids": [(6, 0, cls.env.ref("base.group_portal").ids)],
        })
        cls.portal_user = cls.contact.user_ids

        # Con Jorels, sus datos de facturacion son obligatorios (DECISIONS.md
        # #53): el formulario de cada test los manda validos salvo que el test
        # los pise.
        cls.jorels_values = {}
        if "type_regime_id" in cls.env["res.partner"]._fields:
            liability = cls.env["l10n_co_edi_jorels.type_liabilities"].search([], limit=1)
            liability_ids = [str(liability.id)]
            if cls.env["res.partner"]._fields["type_liability_id"].type == "many2many":
                liability_ids = [""] + liability_ids
            cls.jorels_values = {
                "type_regime_id": str(cls.env["l10n_co_edi_jorels.type_regimes"].search([], limit=1).id),
                "type_liability_id": liability_ids,
                "municipality_id": str(cls.env["l10n_co_edi_jorels.municipalities"].search([], limit=1).id),
                "email_edi": "fe@cafesdelsur.example",
            }
            # El proveedor ya los tiene: mandarlos iguales no es un cambio y no
            # deja nota en el chatter (los tests de documentos cuentan notas).
            cls.supplier.write({
                "type_regime_id": int(cls.jorels_values["type_regime_id"]),
                "type_liability_id": [(6, 0, [liability.id])]
                if cls.env["res.partner"]._fields["type_liability_id"].type == "many2many"
                else liability.id,
                "municipality_id": int(cls.jorels_values["municipality_id"]),
                "email_edi": cls.jorels_values["email_edi"],
            })

        # Proveedor no habilitado en el portal de facturas, con su usuario.
        cls.other_supplier = cls.env["res.partner"].create({
            "name": "OTRO PROVEEDOR SAS",
            "is_company": True,
            "vat": "800111222-7",
            "phone": "6011234567",
            "email": "otro@example.com",
            "street": "Carrera 9",
            "city": "Bogota",
            "zip": "110111",
            "country_id": cls.country.id,
            "company_id": False,
        })
        cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Otro Portal",
            "login": "otro_account",
            "password": "otro_account_pw_2026",
            "partner_id": cls.other_supplier.id,
            "company_id": cls.company.id,
            "company_ids": [(6, 0, cls.company.ids)],
            "group_ids": [(6, 0, cls.env.ref("base.group_portal").ids)],
        })

    # ------------------------------------------------------------------

    def _form(self, partner, **extra):
        data = {
            "name": partner.name,
            "email": partner.email,
            "phone": partner.phone,
            "street": partner.street,
            "city": partner.city,
            "country_id": str(partner.country_id.id),
            # En 19 zip es obligatorio para Colombia (res_country.zip_required):
            # apenas se manda un dato de direccion, los campos obligatorios del
            # pais entran en la validacion. El form real lo preeenvia.
            "zip": partner.zip or "",
        }
        data.update(self.jorels_values)
        data.update(extra)
        return data

    def _post(self, data, files=None):
        """Replica el envio del navegador: el JS manda el form a /my/address/submit."""
        page = self.url_open("/my/account")
        self.assertEqual(page.status_code, 200)
        payload = {}
        for tag in INPUT_RE.findall(page.text):
            attrs = dict(ATTR_RE.findall(tag))
            if attrs.get("type") == "hidden" and attrs.get("name"):
                payload.setdefault(attrs["name"], attrs.get("value", ""))
        self.assertIn("csrf_token", payload, "El formulario no trae csrf_token")
        payload.update(data)  # el data del test manda (p.ej. partner_id ajeno)
        return self.url_open("/my/address/submit", data=payload, files=files or [])

    def _feedback(self, response):
        """JSON de /my/address/submit: redirectUrl si salio bien, si no errores."""
        self.assertEqual(response.status_code, 200, response.text)
        return json.loads(response.text)

    def _doc_notes(self, partner):
        return partner.message_ids.filtered(lambda m: "desde el portal" in (m.body or ""))

    # ------------------------------------------------------------------

    def _skip_unless_jorels(self, installed):
        if ("type_regime_id" in self.env["res.partner"]._fields) != installed:
            self.skipTest("l10n_co_edi_jorels %s instalado" % ("no esta" if installed else "esta"))

    def test_form_shows_documents_without_jorels(self):
        self._skip_unless_jorels(False)
        self.authenticate("ana_account", "ana_account_pw_2026")
        page = self.url_open("/my/account")
        self.assertEqual(page.status_code, 200)
        # Documentos que faltan: label sin label-optional (asterisco, #58).
        for name, _label in portal_account.SPR_DOCUMENTS:
            self.assertRegex(page.text, r'<label class="col-form-label\s*" for="spr_%s"' % name)
        for name, _label in portal_account.SPR_DOCUMENTS:
            self.assertIn('name="%s"' % name, page.text)
        self.assertIn("Sin documento cargado", page.text)
        self.assertNotIn("Facturacion electronica", page.text)
        for name, _label in portal_account.JORELS_FIELDS:
            self.assertNotIn('name="%s"' % name, page.text)

    def test_submit_without_documents(self):
        self.authenticate("ana_account", "ana_account_pw_2026")
        # Asi manda el navegador un input de archivo sin elegir: nombre vacio.
        files = [(name, ("", b"", "application/octet-stream"))
                 for name, _label in portal_account.SPR_DOCUMENTS]
        response = self._post(self._form(self.contact, phone="3109998877"), files)
        feedback = self._feedback(response)
        self.assertEqual(feedback.get("redirectUrl"), "/my")
        # El telefono se escribe normalizado con el pais del partner (portal.py).
        self.assertIn("3109998877", re.sub(r"\D", "", self.contact.phone))
        self.assertFalse(self.supplier.spr_doc_rut_id)
        self.assertFalse(self._doc_notes(self.supplier))

    def test_submit_with_documents_goes_to_commercial_partner(self):
        self.authenticate("ana_account", "ana_account_pw_2026")
        files = [
            ("spr_doc_chamber", ("camara.pdf", PDF, "application/pdf")),
            ("spr_doc_rut", ("rut.pdf", PDF, "application/pdf")),
            ("spr_doc_bank_cert", ("certificado.pdf", PDF, "application/pdf")),
        ]
        response = self._post(self._form(self.contact), files)
        feedback = self._feedback(response)
        self.assertEqual(feedback.get("redirectUrl"), "/my")

        self.assertEqual(self.supplier.spr_doc_chamber_id.raw, PDF)
        self.assertEqual(self.supplier.spr_doc_chamber_id.name, "camara.pdf")
        self.assertEqual(self.supplier.spr_doc_rut_id.raw, PDF)
        self.assertEqual(self.supplier.spr_doc_rut_id.name, "rut.pdf")
        self.assertEqual(self.supplier.spr_doc_bank_cert_id.name, "certificado.pdf")
        # Quedan como adjuntos de la empresa, en el chatter (DECISIONS.md #48).
        attachments = self.env["ir.attachment"].search(
            [("res_model", "=", "res.partner"), ("res_id", "=", self.supplier.id)])
        self.assertIn(self.supplier.spr_doc_rut_id, attachments)
        # Nada en el contacto hijo: los documentos son de la empresa.
        self.assertFalse(self.contact.spr_doc_rut_id)

        notes = self._doc_notes(self.supplier)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes.author_id, self.contact)
        self.assertIn("RUT (rut.pdf)", notes.body)
        self.assertIn("Camara de comercio (camara.pdf)", notes.body)
        self.assertEqual(len(notes.attachment_ids), 3, "Los documentos van en la nota del chatter")

        # El portal muestra el nombre del archivo cargado y, ya cargado, no lo
        # marca como obligatorio (label-optional, sin asterisco).
        page = self.url_open("/my/account")
        self.assertIn("Cargado: <span>rut.pdf</span>", page.text)
        self.assertIn('class="col-form-label label-optional" for="spr_spr_doc_rut"', page.text)
        # Vista previa: el PDF se sirve en linea, solo el del propio proveedor.
        self.assertIn('href="/my/account/document/spr_doc_rut"', page.text)
        preview = self.url_open("/my/account/document/spr_doc_rut")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.headers["Content-Type"], "application/pdf")
        self.assertTrue(preview.headers["Content-Disposition"].startswith("inline"))
        self.assertEqual(preview.content, PDF)
        self.assertEqual(self.url_open("/my/account/document/name").status_code, 404)

    def test_no_upload_keeps_existing_document(self):
        self.supplier._spr_attach_document("spr_doc_rut", "rut_viejo.pdf", PDF)
        self.authenticate("ana_account", "ana_account_pw_2026")
        files = [("spr_doc_rut", ("", b"", "application/octet-stream")),
                 ("spr_doc_bank_cert", ("cert.pdf", PDF, "application/pdf"))]
        response = self._post(self._form(self.contact), files)
        feedback = self._feedback(response)
        self.assertEqual(feedback.get("redirectUrl"), "/my")
        self.assertEqual(self.supplier.spr_doc_rut_id.name, "rut_viejo.pdf")
        self.assertEqual(self.supplier.spr_doc_rut_id.raw, PDF)
        self.assertEqual(self.supplier.spr_doc_bank_cert_id.name, "cert.pdf")
        self.assertNotIn("RUT", self._doc_notes(self.supplier).body)

    def test_rejects_file_too_big(self):
        self.authenticate("ana_account", "ana_account_pw_2026")
        big = PDF + b"0" * 2048
        with patch.object(portal_account, "MAX_DOC_BYTES", 1024):
            response = self._post(
                self._form(self.contact, phone="3000000000"),
                [("spr_doc_rut", ("rut.pdf", big, "application/pdf"))],
            )
        feedback = self._feedback(response)
        self.assertIn("RUT: el PDF supera", " ".join(feedback.get("messages", [])))
        # Con errores no se guarda nada, ni el documento ni el resto.
        self.assertFalse(self.supplier.spr_doc_rut_id)
        self.assertEqual(self.contact.phone, "3001234567")

    def test_rejects_file_type(self):
        self.authenticate("ana_account", "ana_account_pw_2026")
        response = self._post(
            self._form(self.contact),
            [("spr_doc_chamber", ("camara.pdf", b"MZ\x90\x00 no es pdf", "application/pdf"))],
        )
        feedback = self._feedback(response)
        self.assertIn(
            "Camara de comercio: solo se aceptan archivos PDF",
            " ".join(feedback.get("messages", [])),
        )
        self.assertFalse(self.supplier.spr_doc_chamber_id)

    def test_rejects_images_and_password_protected_pdf(self):
        self.authenticate("ana_account", "ana_account_pw_2026")
        response = self._post(self._form(self.contact), [
            ("spr_doc_rut", ("rut.png", PNG, "image/png")),
            ("spr_doc_bank_cert", ("cert.pdf", ENCRYPTED_PDF, "application/pdf")),
        ])
        feedback = self._feedback(response)
        messages = " ".join(feedback.get("messages", []))
        self.assertIn("RUT: solo se aceptan archivos PDF", messages)
        self.assertIn("tiene contrasena o esta protegido", messages)
        self.assertFalse(self.supplier.spr_doc_rut_id or self.supplier.spr_doc_bank_cert_id)

    def test_backend_document_must_be_a_light_pdf_of_the_contact(self):
        with self.assertRaises(ValidationError):
            self.supplier._spr_attach_document("spr_doc_rut", "r.pdf", ENCRYPTED_PDF)
        with self.assertRaises(ValidationError):
            self.supplier._spr_attach_document("spr_doc_chamber", "c.pdf", PNG)
        # Un adjunto de otro contacto no sirve: el documento es de este (#48).
        foreign = self.env["ir.attachment"].create({
            "name": "ajeno.pdf", "raw": PDF, "res_model": "res.partner",
            "res_id": self.other_supplier.id,
        })
        with self.assertRaises(ValidationError):
            self.supplier.spr_doc_chamber_id = foreign
        # Un PDF adjunto en el chatter del contacto se puede elegir.
        own = self.env["ir.attachment"].create({
            "name": "camara.pdf", "raw": PDF, "res_model": "res.partner",
            "res_id": self.supplier.id,
        })
        self.supplier.spr_doc_chamber_id = own
        self.assertEqual(self.supplier.spr_doc_chamber_preview, own.datas)

    def test_preview_needs_an_enabled_supplier_and_a_document(self):
        self.authenticate("ana_account", "ana_account_pw_2026")
        self.assertEqual(self.url_open("/my/account/document/spr_doc_rut").status_code, 404)
        self.supplier._spr_attach_document("spr_doc_rut", "r.pdf", PDF)
        self.assertEqual(self.url_open("/my/account/document/spr_doc_rut").status_code, 200)
        self.supplier.portal_invoice_enabled = False
        self.assertEqual(self.url_open("/my/account/document/spr_doc_rut").status_code, 404)

    def test_jorels_field_is_unknown_without_jorels(self):
        """Sin Jorels el campo no existe en res.partner: en 19 cae en
        ``extra_form_data`` y Odoo lo ignora, sin rechazar el envio. El resto
        del formulario sí se escribe."""
        self._skip_unless_jorels(False)
        self.authenticate("ana_account", "ana_account_pw_2026")
        response = self._post(self._form(self.contact, type_regime_id="1",
                                         phone="3000000000"))
        feedback = self._feedback(response)
        self.assertEqual(feedback.get("redirectUrl"), "/my")
        # El portal escribe el telefono y ademas lo formatea con el pais del
        # partner (portal.py llama a _onchange_phone_validation tras el write).
        self.assertIn("3000000000", re.sub(r"\D", "", self.contact.phone))

    def test_billing_fields_generic_path(self):
        """Sin Jorels, el mismo codigo se prueba con campos estandar de
        res.partner: many2one (industry_id), many2many (category_id) y texto (ref).

        Odoo 19 elimino res.partner.title, por eso el many2one es industry_id
        (campo comercial: al escribirse en el padre Odoo lo baja a los hijos,
        por eso el criterio de "escrito en el comercial" es ref, no industry_id)."""
        industry = self.env["res.partner.industry"].create({"name": "Doctora SPR"})
        tag_a = self.env["res.partner.category"].create({"name": "SPR A"})
        tag_b = self.env["res.partner.category"].create({"name": "SPR B"})
        fields_list = [("industry_id", "Industria"), ("category_id", "Etiquetas"), ("ref", "Referencia")]
        self.authenticate("ana_account", "ana_account_pw_2026")
        with patch.object(portal_account, "JORELS_FIELDS", fields_list):
            page = self.url_open("/my/account")
            self.assertIn("Facturacion electronica", page.text)
            self.assertIn("Doctora SPR", page.text)
            self.assertIn('multiple="multiple"', page.text)
            self.assertIn('name="ref"', page.text)

            # Un id que no existe se rechaza y no se escribe nada.
            response = self._post(self._form(self.contact, industry_id="999999", ref="X"))
            feedback = self._feedback(response)
            self.assertIn(
                "Industria: elija una opcion de la lista.",
                " ".join(feedback.get("messages", [])),
            )
            self.assertIn("industry_id", feedback.get("invalid_fields", []))
            self.assertFalse(self.supplier.industry_id)

            response = self._post(self._form(
                self.contact, industry_id=str(industry.id),
                category_id=["", str(tag_a.id), str(tag_b.id)], ref=" REF-1 ",
            ))
            feedback = self._feedback(response)
            self.assertEqual(feedback.get("redirectUrl"), "/my")
        # Se escribe en el comercial (industry_id y ref via nuestro handler).
        self.assertEqual(self.supplier.industry_id, industry)
        self.assertEqual(self.supplier.category_id, tag_a | tag_b)
        self.assertEqual(self.supplier.ref, "REF-1")
        # ref no es comercial: si se hubiera escrito en el contacto no llegaria aqui.
        self.assertFalse(self.contact.ref)
        self.assertIn("Industria", self._doc_notes(self.supplier).body)

    def test_jorels_fields_when_installed(self):
        """Solo corre en una base con l10n_co_edi_jorels."""
        self._skip_unless_jorels(True)
        regime = self.env["l10n_co_edi_jorels.type_regimes"].search([], limit=1)
        liability = self.env["l10n_co_edi_jorels.type_liabilities"].search([], limit=1)
        municipality = self.env["l10n_co_edi_jorels.municipalities"].search([], limit=1)
        self.assertTrue(regime and liability and municipality, "Faltan las listas de Jorels")
        self.authenticate("ana_account", "ana_account_pw_2026")
        page = self.url_open("/my/account")
        self.assertIn("Facturacion electronica", page.text)
        for name, _label in portal_account.JORELS_FIELDS:
            self.assertIn('name="%s"' % name, page.text)
            # Obligatorios con asterisco: label sin label-optional y el input
            # marcado para que el JS le devuelva el required (#58).
            self.assertRegex(page.text, r'<label class="col-form-label" for="spr_%s"' % name)
            self.assertRegex(
                page.text,
                r'<(?:input|select)\b(?=[^>]*name="%s")(?=[^>]*data-spr-required="1")' % name)
        self.assertIn(municipality.display_name, page.text)

        response = self._post(self._form(self.contact, email_edi="no-es-correo"))
        feedback = self._feedback(response)
        self.assertIn(
            "Email de facturacion: el correo no es valido.",
            " ".join(feedback.get("messages", [])),
        )
        self.assertIn("email_edi", feedback.get("invalid_fields", []))

        liability_ids = [str(liability.id)]
        if self.env["res.partner"]._fields["type_liability_id"].type == "many2many":
            liability_ids = [""] + liability_ids
        response = self._post(self._form(
            self.contact, type_regime_id=str(regime.id), type_liability_id=liability_ids,
            municipality_id=str(municipality.id), email_edi="fe@cafesdelsur.example",
        ))
        feedback = self._feedback(response)
        self.assertEqual(feedback.get("redirectUrl"), "/my")
        self.assertEqual(self.supplier.type_regime_id, regime)
        self.assertEqual(self.supplier.type_liability_id, liability)
        self.assertEqual(self.supplier.municipality_id, municipality)
        self.assertEqual(self.supplier.email_edi, "fe@cafesdelsur.example")

    def test_jorels_fields_are_required(self):
        """Solo con Jorels: vacios o ausentes del POST no se guarda nada."""
        self._skip_unless_jorels(True)
        self.authenticate("ana_account", "ana_account_pw_2026")
        page = self.url_open("/my/account")
        email_tag = next(tag for tag in INPUT_RE.findall(page.text) if 'name="email_edi"' in tag)
        self.assertIn('required="required"', email_tag)
        data = self._form(self.contact, type_regime_id="", email_edi="")
        data.pop("municipality_id")
        feedback = self._feedback(self._post(
            data, [("spr_doc_rut", ("rut.pdf", PDF, "application/pdf"))]))
        messages = " ".join(feedback.get("messages", []))
        for label in ("Tipo de regimen", "Municipio", "Email de facturacion"):
            self.assertIn("%s: es obligatorio." % label, messages)
        self.assertTrue({"type_regime_id", "municipality_id", "email_edi"}
                        <= set(feedback.get("invalid_fields", [])))
        self.assertFalse(feedback.get("redirectUrl"))
        self.assertFalse(self.supplier.spr_doc_rut_id)

    def test_cannot_write_other_partner(self):
        self.authenticate("ana_account", "ana_account_pw_2026")
        # Un partner ajeno: Odoo 19 levanta Forbidden en /my/address/submit
        # antes de validar o escribir nada.
        response = self._post(
            self._form(self.contact, partner_id=str(self.other_supplier.id)),
            [("spr_doc_rut", ("rut.pdf", PDF, "application/pdf"))],
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.other_supplier.spr_doc_rut_id)
        self.assertFalse(self.supplier.spr_doc_rut_id)

        # Por ORM el usuario portal no escribe ningun contacto ni lee los documentos.
        portal_env = self.env(user=self.portal_user)
        with self.assertRaises(AccessError):
            self.other_supplier.with_env(portal_env).write({"spr_doc_rut_id": False})
        with self.assertRaises(AccessError):
            self.supplier.with_env(portal_env).read(["spr_doc_rut_id"])

    def test_not_enabled_supplier_has_standard_form(self):
        self.authenticate("otro_account", "otro_account_pw_2026")
        page = self.url_open("/my/account")
        self.assertNotIn('name="spr_doc_rut"', page.text)
        # Sin proveedor habilitado no hay validacion de documentos: el archivo
        # se descarta (queda en extra_form_data) y el envio termina bien.
        response = self._post(self._form(self.other_supplier),
                              [("spr_doc_rut", ("rut.pdf", PDF, "application/pdf"))])
        feedback = self._feedback(response)
        self.assertEqual(feedback.get("redirectUrl"), "/my")
        self.assertFalse(self.other_supplier.spr_doc_rut_id)

    def test_child_still_cannot_change_vat(self):
        """El bloqueo estandar de NIT para contactos hijos sigue igual."""
        self.authenticate("ana_account", "ana_account_pw_2026")
        response = self._post(self._form(self.contact, vat="999999999"),
                              [("spr_doc_rut", ("rut.pdf", PDF, "application/pdf"))])
        feedback = self._feedback(response)
        self.assertFalse(feedback.get("redirectUrl"))
        self.assertIn("vat", feedback.get("invalid_fields", []))
        self.assertEqual(self.supplier.vat, "900123456-8")
        self.assertFalse(self.supplier.spr_doc_rut_id)
