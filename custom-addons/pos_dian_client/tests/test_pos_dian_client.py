# -*- coding: utf-8 -*-
import requests
from unittest.mock import patch

from odoo import _
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user


class TestPosDianClient(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"]
        cls.company = cls.env.company
        cls.company.api_key = "TOKEN-TEST"
        cls.company.ei_enable = True
        cls.company.ei_set_default_partner_data = False
        cls.company.country_id = cls.env.ref("base.co")
        municipalities = cls.env["l10n_co_edi_jorels.municipalities"]
        cls.municipality = municipalities.search([], limit=1)
        if not cls.municipality:
            cls.env["res.company"].init_csv_data(
                "l10n_co_edi_jorels.l10n_co_edi_jorels.municipalities"
            )
            cls.municipality = municipalities.search([], limit=1)
        cls.company.partner_id.municipality_id = cls.municipality
        cls.regime = cls.env["l10n_co_edi_jorels.type_regimes"].browse(2)
        cls.liability = cls.env["l10n_co_edi_jorels.type_liabilities"].browse(29)
        cls.assertTrue(cls.regime.exists(), "el listado de regímenes debe cargarse")
        cls.assertTrue(cls.liability.exists(), "el listado de responsabilidades debe cargarse")
        cls.rut_type = cls.env["l10n_latam.identification.type"].search(
            [("l10n_co_document_code", "=", "rut")], limit=1
        )
        cls.cc_type = cls.env["l10n_latam.identification.type"].search(
            [("l10n_co_document_code", "=", "national_citizen_id")], limit=1
        )
        cls.portal_user = new_test_user(
            cls.env, login="portal.qa", groups="base.group_portal"
        )
        # Base NIT y DV reales del algoritmo (verificados: 900123456-8,
        # 901234567-7). Usamos uno distinto al demo para evitar colisiones.
        cls.NIT_BASE = "951753951"
        cls.NIT_DV = cls.partner._pos_dian_nit_dv(cls.NIT_BASE)
        cls.CC_NUMBER = "1098765432"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _mock(self, mock_post, payload, status_code=200):
        mock_post.return_value.json.return_value = payload
        mock_post.return_value.status_code = status_code

    def _full_existing(self, vat=None, name="Empresa Ya Cargada SAS"):
        """Partner completo para FE. Si `vat` no es la forma canónica (simula
        filas heredadas), se escribe por SQL: el ORM de l10n_co ya no permite
        guardar ese formato."""
        canonical = "%s-%s" % (self.NIT_BASE, self.NIT_DV)
        partner = self.env["res.partner"].create(
            {
                "name": name,
                "vat": canonical,
                "l10n_latam_identification_type_id": self.rut_type.id,
                "is_company": True,
                "email_edi": "previo@x.co",
                "type_regime_id": self.regime.id,
                "type_liability_id": self.liability.id,
                "municipality_id": self.municipality.id,
                "country_id": self.env.ref("base.co").id,
            }
        )
        if vat and vat != canonical:
            self.env.cr.execute(
                "UPDATE res_partner SET vat = %s WHERE id = %s", (vat, partner.id)
            )
            partner.invalidate_recordset()
        return partner

    def _lookup(self, doc_code="rut", number=None, dv=False):
        return self.partner.pos_dian_lookup(doc_code, number or self.NIT_BASE, dv)

    def _confirm(self, action="assign", **kw):
        return self.partner.pos_dian_confirm(
            kw.pop("doc_code", "rut"),
            kw.pop("number", self.NIT_BASE),
            kw.pop("dv", False),
            action,
            **kw,
        )

    # ── Algoritmo DV ──────────────────────────────────────────────────────────

    def test_nit_dv(self):
        self.assertEqual(self.partner._pos_dian_nit_dv("900123456"), "8")
        self.assertEqual(self.partner._pos_dian_nit_dv("901234567"), "7")

    # ── Guardias ──────────────────────────────────────────────────────────────

    def test_guard_forbids_non_pos_users(self):
        with self.assertRaises(AccessError):
            self.partner.with_user(self.portal_user).pos_dian_client_doc_types()
        with self.assertRaises(AccessError):
            self.partner.with_user(self.portal_user).pos_dian_lookup("rut", self.NIT_BASE)

    def test_doc_types(self):
        codes = {t["code"] for t in self.partner.pos_dian_client_doc_types()}
        self.assertIn("national_citizen_id", codes)
        self.assertIn("rut", codes)
        self.assertIn("external_id", codes)
        self.assertIn("passport", codes)
        self.assertNotIn("vat", codes, "NIF duplica al NIT: mismo tipo DIAN 6")

    def test_no_token_config_error(self):
        self.company.api_key = False
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            res = self._lookup()
        self.assertEqual(res["status"], "config_error")
        mock_post.assert_not_called()

    def test_ei_disabled_config_error(self):
        self.company.ei_enable = False
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            res = self._lookup()
        self.assertEqual(res["status"], "config_error")
        mock_post.assert_not_called()

    # ── Clasificación de Edipo ────────────────────────────────────────────────

    def test_not_registered(self):
        # Formato real de Edipo para "no registrado" (sondeo 2026-10-13):
        # message con name y email nulos. Edipo no usa `detail` para esto.
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"message": "El número no aparece en la DIAN",
                                   "name": None, "email": None})
            res = self._lookup()
        self.assertEqual(res["status"], "not_registered")

    def test_detail_string_is_unexpected_not_not_registered(self):
        # Un `detail` SIEMPRE es error del servicio/forma, jamás "no registrado".
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"detail": "Error interno del servicio"})
            res = self._lookup()
        self.assertEqual(res["status"], "unexpected_response")

    def test_unauthenticated_http_200_is_config_error(self):
        # Sondeo real 2026-10-13: el error de token llega con HTTP 200.
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"message": "Unauthenticated."})
            res = self._lookup()
        self.assertEqual(res["status"], "config_error")

    def test_message_with_null_name_email_is_not_registered(self):
        # Cualquier message sin datos de adquirente clasifica como
        # "no registrado" (decisión 2026-10-13: el formato real de Edipo).
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"message": "Servicio temporalmente indisponible",
                                   "name": None, "email": None})
            res = self._lookup()
        self.assertEqual(res["status"], "not_registered")

    def test_validation_detail_list_is_unexpected(self):
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"detail": [{"loc": ["query", "token"], "msg": "Field required"}]})
            res = self._lookup()
        self.assertEqual(res["status"], "unexpected_response")

    def test_timeout_is_connection_error(self):
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            mock_post.side_effect = requests.Timeout("boom")
            res = self._lookup()
        self.assertEqual(res["status"], "connection_error")

    def test_invalid_dv_blocks_before_http(self):
        wrong_dv = str((int(self.NIT_DV) + 1) % 10)
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            res = self._lookup(dv=wrong_dv)
        self.assertEqual(res["status"], "invalid")
        self.assertIn(self.NIT_DV, res["detail"])
        mock_post.assert_not_called()

    # ── NIT con DV pegado (regla 2026-10-13) ─────────────────────────────────

    def test_nit_with_attached_dv(self):
        attached = "%s%s" % (self.NIT_BASE, self.NIT_DV)
        r = self.partner._pos_dian_resolve("rut", attached)
        self.assertEqual(r["query_number"], self.NIT_BASE)
        self.assertEqual(r["vat_expected"], "%s-%s" % (self.NIT_BASE, self.NIT_DV))
        # DV digitado aparte: se toma literal y se verifica como siempre.
        r2 = self.partner._pos_dian_resolve("rut", self.NIT_BASE, dv=self.NIT_DV)
        self.assertEqual(r2["query_number"], self.NIT_BASE)
        self.assertEqual(r2["vat_expected"], "%s-%s" % (self.NIT_BASE, self.NIT_DV))
        # 10 dígitos empezando por 1 (perfil de CC): NO se interpreta como
        # NIT+DV aunque el cajero haya elegido NIT.
        r3 = self.partner._pos_dian_resolve("rut", self.CC_NUMBER)
        self.assertEqual(r3["query_number"], self.CC_NUMBER)

    def test_consumidor_final_generic_is_invalid(self):
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            res = self._lookup(number="222222222222")
        self.assertEqual(res["status"], "invalid")
        mock_post.assert_not_called()

    # ── Lookup sobre existentes ───────────────────────────────────────────────

    def test_existing_complete_is_found_without_writes(self):
        existing = self._full_existing("%s-%s" % (self.NIT_BASE, self.NIT_DV))
        self.env.flush_all()
        write_date = existing.write_date
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"name": existing.name, "email": existing.email_edi})
            res = self._lookup()
        self.assertEqual(res["status"], "found")
        self.assertFalse(res["missing"])
        self.assertFalse(res["fillable"])
        self.assertFalse(res["diff"]["name"])
        res2 = self._confirm(action="assign")
        self.assertEqual(res2["status"], "assigned")
        self.assertEqual(res2["partner_id"], existing.id)
        self.env.flush_all()
        self.assertEqual(existing.write_date, write_date, "assign no debe tocar el registro")

    def test_existing_vat_without_dv_is_found_and_fillable(self):
        existing = self._full_existing(self.NIT_BASE)
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"name": existing.name, "email": existing.email_edi})
            res = self._lookup()
        self.assertEqual(res["status"], "found")
        self.assertEqual(res["fillable"].get("vat"), "%s-%s" % (self.NIT_BASE, self.NIT_DV))
        out = self._confirm(action="update", dian_name=existing.name, dian_email=existing.email_edi)
        self.assertEqual(out["status"], "updated")
        existing.invalidate_recordset()
        self.assertEqual(existing.vat, "%s-%s" % (self.NIT_BASE, self.NIT_DV))

    def test_existing_no_email_fills_email_edi_only(self):
        existing = self._full_existing("%s-%s" % (self.NIT_BASE, self.NIT_DV))
        existing.write({"email_edi": False, "email": False})
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"name": "Nombre Distinto DIAN", "email": "nueva@x.co"})
            res = self._lookup()
        self.assertEqual(res["status"], "found")
        self.assertEqual(res["fillable"].get("email_edi"), "nueva@x.co")
        self.assertTrue(res["diff"]["name"])
        out = self._confirm(action="update", dian_name="Nombre Distinto DIAN",
                            dian_email="nueva@x.co", replace=False)
        existing.invalidate_recordset()
        self.assertEqual(out["status"], "updated")
        self.assertEqual(existing.email_edi, "nueva@x.co")
        self.assertEqual(existing.name, "Empresa Ya Cargada SAS", "sin replace no se pisa el nombre")

    def test_replace_updates_name_and_emails(self):
        existing = self._full_existing("%s-%s" % (self.NIT_BASE, self.NIT_DV))
        out = self._confirm(action="update", dian_name="Otra Razon SA",
                            dian_email="otro@x.co", replace=True)
        self.assertEqual(out["status"], "updated")
        existing.invalidate_recordset()
        self.assertEqual(existing.name, "Otra Razon SA")
        self.assertEqual(existing.email, "otro@x.co")
        self.assertEqual(existing.email_edi, "otro@x.co")

    def test_existing_missing_regime_is_fillable(self):
        existing = self._full_existing("%s-%s" % (self.NIT_BASE, self.NIT_DV))
        existing.write({"type_regime_id": False})
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"name": existing.name, "email": "x@y.co"})
            res = self._lookup()
        self.assertEqual(res["status"], "found")
        self.assertEqual(res["fillable"].get("type_regime_id"), self.regime.id)
        out = self._confirm(action="update", dian_name=existing.name, dian_email="x@y.co")
        self.assertEqual(out["status"], "updated")
        existing.invalidate_recordset()
        self.assertEqual(existing.type_regime_id, self.regime)

    def test_existing_missing_fields_filled_from_defaults(self):
        existing = self._full_existing("%s-%s" % (self.NIT_BASE, self.NIT_DV))
        existing.write({
            "type_regime_id": False,
            "type_liability_id": False,
            "municipality_id": False,
        })
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"name": existing.name, "email": existing.email_edi})
            res = self._lookup()
        self.assertEqual(res["status"], "found")
        self.assertFalse(res["missing"])
        self.assertEqual(res["fillable"].get("type_regime_id"), self.regime.id)
        self.assertEqual(res["fillable"].get("type_liability_id"), self.liability.id)
        self.assertEqual(res["fillable"].get("municipality_id"), self.municipality.id)
        out = self._confirm(action="update", dian_name=existing.name,
                            dian_email=existing.email_edi)
        self.assertEqual(out["status"], "updated")
        existing.invalidate_recordset()
        self.assertEqual(existing.type_regime_id, self.regime)
        self.assertEqual(existing.type_liability_id, self.liability)
        self.assertEqual(existing.municipality_id, self.municipality)
        self.assertEqual(existing.email_edi, "previo@x.co", "no se pisa lo que ya tenía valor")

    def test_company_without_municipality_blocks_when_partner_lacks(self):
        self.company.partner_id.municipality_id = False
        existing = self._full_existing("%s-%s" % (self.NIT_BASE, self.NIT_DV))
        existing.write({"municipality_id": False})
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"name": existing.name, "email": existing.email_edi})
            res = self._lookup()
        self.assertEqual(res["status"], "incomplete")
        self.assertIn("municipio", res["missing"][0])

    def test_archived_single_match_blocks(self):
        existing = self._full_existing("%s-%s" % (self.NIT_BASE, self.NIT_DV))
        existing.active = False
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"name": existing.name, "email": "x@y.co"})
            res = self._lookup()
        self.assertEqual(res["status"], "archived")
        out = self._confirm(action="assign")
        self.assertEqual(out["status"], "ambiguous")

    def test_type_mismatch_blocks(self):
        # Persona existente con CC y el mismo número; se consulta como NIT.
        cc_partner = self.env["res.partner"].create(
            {
                "name": "Persona Con CC",
                "l10n_latam_identification_type_id": self.cc_type.id,
                "is_company": False,
                "email_edi": "cc@x.co",
                "type_regime_id": self.regime.id,
                "type_liability_id": self.liability.id,
                "municipality_id": self.municipality.id,
                "country_id": self.env.ref("base.co").id,
            }
        )
        self.env.cr.execute(
            "UPDATE res_partner SET vat = %s WHERE id = %s", (self.NIT_BASE, cc_partner.id)
        )
        cc_partner.invalidate_recordset()
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"name": "Empresa NIT SA", "email": "n@x.co"})
            res = self._lookup()
        self.assertEqual(res["status"], "type_mismatch")
        self.assertIn("Cédula", res["detail"])
        self.assertEqual(res["partner"]["id"], cc_partner.id)
        # Ni assign ni create escriben nada.
        out = self._confirm(action="assign")
        self.assertEqual(out["status"], "type_mismatch")
        out2 = self._confirm(action="create", dian_name="Empresa NIT SA", dian_email="n@x.co")
        self.assertEqual(out2["status"], "type_mismatch")
        cc_partner.invalidate_recordset()
        self.assertEqual(cc_partner.name, "Persona Con CC")

    def test_non_nit_vat_is_never_rewritten(self):
        # CC guardada con puntos (fila legacy): se encuentra, pero su vat no
        # se reescribe (solo el NIT sin DV/guion se normaliza).
        cc_partner = self.env["res.partner"].create(
            {
                "name": "Persona CC Puntos",
                "l10n_latam_identification_type_id": self.cc_type.id,
                "is_company": False,
                "email_edi": "cc2@x.co",
                "type_regime_id": self.regime.id,
                "type_liability_id": self.liability.id,
                "municipality_id": self.municipality.id,
                "country_id": self.env.ref("base.co").id,
            }
        )
        self.env.cr.execute(
            "UPDATE res_partner SET vat = '10.987.654.32', edi_sanitize_vat = %s WHERE id = %s",
            (self.CC_NUMBER, cc_partner.id),
        )
        cc_partner.invalidate_recordset()
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"name": "Persona CC Puntos", "email": "cc2@x.co"})
            res = self._lookup(doc_code="national_citizen_id", number=self.CC_NUMBER)
        self.assertEqual(res["status"], "found")
        self.assertNotIn("vat", res["fillable"])
        out = self._confirm(action="update", doc_code="national_citizen_id",
                            number=self.CC_NUMBER,
                            dian_name="Persona CC Puntos", dian_email="cc2@x.co")
        self.assertEqual(out["status"], "updated")
        cc_partner.invalidate_recordset()
        self.assertEqual(cc_partner.vat, "10.987.654.32", "el vat no vacío no se reescribe")

    def test_savepoint_reverts_create_on_failure(self):
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post"):
            with patch.object(
                type(self.env["res.partner"]), "message_post",
                side_effect=RuntimeError("boom"),
            ):
                out = self.partner.pos_dian_confirm(
                    "rut", self.NIT_BASE, False, "create",
                    dian_name="Fallida SA", dian_email="f@x.co",
                )
        self.assertEqual(out["status"], "unexpected_response")
        self.assertFalse(
            self.partner.search([("vat", "=", "%s-%s" % (self.NIT_BASE, self.NIT_DV))]),
            "el savepoint debe haber revertido la creación",
        )

    def test_ambiguous_two_partners(self):
        a = self._full_existing()
        b = self._full_existing(name="Duplicado SA")
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"name": a.name, "email": "x@y.co"})
            res = self._lookup()
        self.assertEqual(res["status"], "ambiguous")
        self.assertEqual(len(res["candidates"]), 2)

    def test_partner_without_latam_type_is_found(self):
        plain = self.env["res.partner"].create(
            {
                "name": "Sin Tipo SA",
                "l10n_latam_identification_type_id": False,
                "is_company": True,
                "email_edi": "viejito@x.co",
                "type_regime_id": self.regime.id,
                "type_liability_id": self.liability.id,
                "municipality_id": self.municipality.id,
                "country_id": self.env.ref("base.co").id,
            }
        )
        self.env.cr.execute(
            "UPDATE res_partner SET vat = %s WHERE id = %s", (self.NIT_BASE, plain.id)
        )
        plain.invalidate_recordset()
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"name": plain.name, "email": plain.email_edi})
            res = self._lookup()
        self.assertEqual(res["status"], "found")
        self.assertEqual(res["partner"]["id"], plain.id)
        self.assertIn("l10n_latam_identification_type_id", res["fillable"])

    # ── Creación ──────────────────────────────────────────────────────────────

    def test_create_flow(self):
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"name": "Nueva Empresa SAS", "email": "nueva@x.co"})
            res = self._lookup()
        self.assertEqual(res["status"], "create_ok")
        out = self._confirm(action="create", dian_name="Nueva Empresa SAS",
                            dian_email="nueva@x.co")
        self.assertEqual(out["status"], "created")
        partner = self.env["res.partner"].browse(out["partner_id"])
        self.assertEqual(partner.vat, "%s-%s" % (self.NIT_BASE, self.NIT_DV))
        self.assertTrue(partner.is_company)
        self.assertEqual(partner.email, "nueva@x.co")
        self.assertEqual(partner.email_edi, "nueva@x.co")
        self.assertEqual(partner.type_regime_id, self.regime)
        self.assertEqual(partner.type_liability_id, self.liability)
        self.assertEqual(partner.municipality_id, self.municipality)
        self.assertTrue(partner.message_ids, "debe quedar nota en el chatter")
        url = mock_post.call_args[0][0]
        self.assertIn("/acquirer/6/%s" % self.NIT_BASE, url)

    def test_needs_email_flow(self):
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"name": "Sin Correo SA", "email": "sininformacion@correo.com"})
            res = self._lookup()
        self.assertEqual(res["status"], "needs_email")
        refused = self._confirm(action="create", dian_name="Sin Correo SA")
        self.assertEqual(refused["status"], "needs_email")
        out = self._confirm(action="create", dian_name="Sin Correo SA", email="p@x.co")
        self.assertEqual(out["status"], "created")
        partner = self.env["res.partner"].browse(out["partner_id"])
        self.assertEqual(partner.email, "p@x.co")

    def test_create_person_keeps_dian_name(self):
        # El nombre de la DIAN se guarda tal cual (solo colapsando espacios
        # dobles): reordenarlo con coma sería adivinar el orden.
        out = self.partner.pos_dian_confirm(
            "national_citizen_id", self.CC_NUMBER, False, "create",
            dian_name="PEREZ  PEREZ JUAN", dian_email="jp@x.co",
        )
        self.assertEqual(out["status"], "created")
        partner = self.env["res.partner"].browse(out["partner_id"])
        self.assertEqual(partner.name, "PEREZ PEREZ JUAN")
        self.assertFalse(partner.is_company)

    def test_permission_error_on_create(self):
        cash = new_test_user(
            self.env, login="caja.sin.creation",
            groups="base.group_user,point_of_sale.group_pos_user",
        )
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post"):
            out = self.partner.with_user(cash).pos_dian_confirm(
                "rut", self.NIT_BASE, False, "create",
                dian_name="Alguien SAS", dian_email="a@b.co",
            )
        self.assertEqual(out["status"], "permission_error")

    # ── Configuración del botón (flags de pos.config) ────────────────────────

    def test_dian_button_flags(self):
        defaults = self.env["pos.config"].default_get(
            ["show_dian_client_button", "hide_partner_button"]
        )
        self.assertTrue(defaults["show_dian_client_button"])
        self.assertFalse(defaults["hide_partner_button"],
                         "ocultar el cliente nativo debe ser opt-in")
        config = self.env["pos.config"].search([], limit=1)
        if config:
            config.hide_partner_button = True
            self.assertTrue(config.hide_partner_button)
            config.hide_partner_button = False

    # ── Errores de validación de Edipo, largo y correos (QA 2026-10-14) ──────

    def test_edipo_validation_errors_are_unexpected(self):
        # Sondeo real: un número inválido llega con `message` + `errors` y no
        # debe presentarse como "no registrado".
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {
                "message": "El campo identification number sólo debe contener letras, "
                           "números, guiones y guiones bajos.",
                "errors": {"identification_number": ["..."]},
            })
            res = self._lookup()
        self.assertEqual(res["status"], "unexpected_response")

    def test_detail_list_hides_raw_payload(self):
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            self._mock(mock_post, {"detail": [{"type": "int_parsing", "input": "AB123456"}]}, 422)
            res = self._lookup()
        self.assertEqual(res["status"], "unexpected_response")
        self.assertNotIn("int_parsing", res["detail"])

    def test_too_long_number_is_invalid_before_http(self):
        with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
            res = self.partner.pos_dian_lookup("national_citizen_id", "1" * 40)
            res_nit = self._lookup(number="9" * 20)
        self.assertEqual(res["status"], "invalid")
        self.assertEqual(res_nit["status"], "invalid")
        mock_post.assert_not_called()

    def test_placeholder_dian_email_asks_for_email(self):
        for placeholder in ("SINCORREO@GMAIL.COM", "sincorreo@sincorreo.com"):
            with patch("odoo.addons.pos_dian_client.models.res_partner.requests.post") as mock_post:
                self._mock(mock_post, {"name": "Alguien SAS", "email": placeholder})
                res = self._lookup()
            self.assertEqual(res["status"], "needs_email", placeholder)

    def test_invalid_typed_email_is_rejected(self):
        for bad in ("a@", "@", "foo", "a b@x.co"):
            out = self._confirm(action="create", dian_name="Alguien SAS", email=bad)
            self.assertEqual(out["status"], "invalid", bad)
        self.assertFalse(self.env["res.partner"].search_count(
            [("vat", "=", "%s-%s" % (self.NIT_BASE, self.NIT_DV))]))
