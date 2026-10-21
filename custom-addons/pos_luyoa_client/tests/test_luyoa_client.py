# -*- coding: utf-8 -*-
import requests
from unittest.mock import patch

import psycopg2

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user
from odoo.tools import mute_logger

MODULE = "odoo.addons.pos_luyoa_client.models.res_partner"

# UID real del QR de prueba escaneado (2026-10-19): el QR de la tarjeta
# apunta a https://demo.luyoa.com/c/sFpY-5uqfH6gPzIKWgbmR
TEST_UID = "sFpY-5uqfH6gPzIKWgbmR"
TEST_URL = "https://demo.luyoa.com/c/%s" % TEST_UID

LUYOA_CUSTOMER = {
    "success": True,
    "data": {
        "firstName": "Pedro",
        "lastName": "Páramo",
        "email": "pedro@example.com",
        "phoneNumber": "5512345678",
        "totalBalance": 15,
        "currentBalance": 5,
        "rewards": [],
    },
}


class TestPosLuyoaClient(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.config = cls.env["pos.config"].create({
            "name": "Tienda Luyoa",
            "luyoa_client_enabled": True,
            "luyoa_base_url": "https://api.luyoa.test",
            "luyoa_integration_uid": "int-uid-test",
            "luyoa_business_uid": "biz-uid-test",
            "luyoa_api_token": "token-test",
        })
        cls.portal_user = new_test_user(
            cls.env, login="portal.luyoa", groups="base.group_portal"
        )
        cls.cashier = new_test_user(
            cls.env, login="cajero.luyoa",
            groups="base.group_user,point_of_sale.group_pos_user,base.group_partner_manager",
        )
        cls.pos_manager = new_test_user(
            cls.env, login="admin.pos.luyoa",
            groups="base.group_user,point_of_sale.group_pos_manager",
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _mock(self, mock_get, payload, status_code=200):
        mock_get.return_value.json.return_value = payload
        mock_get.return_value.status_code = status_code

    def _lookup(self, text=TEST_UID):
        return self.partner_model.pos_luyoa_lookup(text, self.config.id)

    def _assign(self, action="assign", text=TEST_UID):
        return self.partner_model.pos_luyoa_assign(text, self.config.id, action)

    # ── Extracción del customerUID ────────────────────────────────────────────

    def test_extract_uid_from_wallet_url(self):
        """El QR de la tarjeta (Apple/Google Wallet) apunta a .../c/<uid>."""
        self.assertEqual(self.partner_model._pos_luyoa_extract_uid(TEST_URL), TEST_UID)

    def test_extract_uid_from_bare_uid(self):
        self.assertEqual(self.partner_model._pos_luyoa_extract_uid(TEST_UID), TEST_UID)

    def test_extract_uid_rejects_garbage(self):
        self.assertFalse(self.partner_model._pos_luyoa_extract_uid("hola mundo"))
        self.assertFalse(self.partner_model._pos_luyoa_extract_uid(""))
        self.assertFalse(self.partner_model._pos_luyoa_extract_uid(False))
        # UID demasiado corto: no calza con el formato real de Luyoa.
        self.assertFalse(self.partner_model._pos_luyoa_extract_uid("corto123"))

    def test_extract_uid_from_url_with_query(self):
        url = "https://demo.luyoa.com/c/%s?utm=pos" % TEST_UID
        self.assertEqual(self.partner_model._pos_luyoa_extract_uid(url), TEST_UID)

    # ── Guardias ──────────────────────────────────────────────────────────────

    def test_guard_forbids_non_pos_users(self):
        with self.assertRaises(AccessError):
            self.partner_model.with_user(self.portal_user).pos_luyoa_lookup(TEST_UID, self.config.id)
        with self.assertRaises(AccessError):
            self.partner_model.with_user(self.portal_user).pos_luyoa_assign(TEST_UID, self.config.id)

    # ── Configuración ─────────────────────────────────────────────────────────

    def test_lookup_without_config(self):
        self.config.luyoa_client_enabled = False
        res = self._lookup()
        self.assertEqual(res["status"], "config_error")
        self.config.luyoa_client_enabled = True
        self.config.luyoa_api_token = False
        res = self._lookup()
        self.assertEqual(res["status"], "config_error")
        self.assertIn("token", res["detail"])

    def test_base_url_default(self):
        """Las tiendas nuevas nacen con la URL del entorno donde está
        registrado el negocio (demo)."""
        config = self.env["pos.config"].create({"name": "Tienda default URL"})
        self.assertEqual(config.luyoa_base_url, "https://demo.luyoa.com/api/external/v1")

    def test_base_url_change_warns(self):
        """Cambiar la URL ya guardada muestra una advertencia en el formulario."""
        with self.env.cr.savepoint():
            record = self.config.new(origin=self.config)
            record.luyoa_base_url = "https://app.luyoa.com/api/external/v1"
            res = record._onchange_luyoa_base_url()
        self.assertTrue(res and res.get("warning"))

    # ── Seguridad de las credenciales ─────────────────────────────────────────

    def _pos_config_data(self, user):
        config = self.config.with_user(user)
        return config._load_pos_data_read(config, config)[0]

    def test_secrets_not_sent_to_pos(self):
        """Ni el cajero ni el responsable del POS reciben las credenciales en
        la carga de datos del navegador; solo el interruptor del botón."""
        for user in (self.cashier, self.pos_manager):
            data = self._pos_config_data(user)
            self.assertTrue(data["luyoa_client_enabled"])
            for fname in ("luyoa_api_token", "luyoa_integration_uid", "luyoa_business_uid"):
                self.assertNotIn(fname, data, "%s llegó al POS de %s" % (fname, user.login))

    def test_cashier_cannot_read_token(self):
        with self.assertRaises(AccessError):
            self.config.with_user(self.cashier).read(["luyoa_api_token"])

    def test_cashier_lookup_uses_server_credentials(self):
        """El cajero no lee el token, pero la consulta (servidor) sí lo usa."""
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            res = self.partner_model.with_user(self.cashier).pos_luyoa_lookup(TEST_UID, self.config.id)
        self.assertEqual(res["status"], "not_in_odoo")
        self.assertEqual(mock_get.call_args[1]["headers"]["Authorization"], "Bearer token-test")

    def test_lookup_invalid_uid(self):
        res = self._lookup(text="no es un uid")
        self.assertEqual(res["status"], "invalid_uid")

    # ── Lookup contra el API (mockeado) ───────────────────────────────────────

    def test_lookup_found_by_email(self):
        self.env["res.partner"].create({
            "name": "Pedro Páramo",
            "email": "Pedro@Example.com",
        })
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            res = self._lookup()
        self.assertEqual(res["status"], "found")
        self.assertEqual(res["match_by"], "email")
        self.assertTrue(res["partner"])
        # El correo de Luyoa se compara sin distinguir mayúsculas.
        self.assertEqual(res["luyoa"]["email"], "pedro@example.com")

    def test_lookup_phone_with_spaces_does_not_match(self):
        """El fallback por teléfono compara dígitos contra el valor guardado:
        un teléfono con espacios ("+52 55 1234 5678") no calza con ILIKE
        '%5512345678%' (comportamiento documentado; el correo es la clave
        principal y el UID guardado resuelve los próximos escaneos).
        El nombre del contacto es distinto al de Luyoa para que tampoco
        matchee el fallback por nombre."""
        self.env["res.partner"].create({
            "name": "Cliente Con Espacios",
            "phone": "+52 55 1234 5678",
        })
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            res = self._lookup()
        self.assertEqual(res["status"], "not_in_odoo")

    def test_lookup_found_by_name_and_phone(self):
        """Nombre Y teléfono juntos identifican al cliente (teléfono con
        prefijo internacional incluido)."""
        self.env["res.partner"].create({
            "name": "Pedro Páramo",
            "phone": "+525512345678",
        })
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            res = self._lookup()
        self.assertEqual(res["status"], "found")
        self.assertEqual(res["match_by"], "name_phone")

    def test_lookup_name_only_is_not_enough(self):
        """Solo el nombre no identifica: se ofrece crear, no asignar."""
        self.env["res.partner"].create({"name": "Pedro Páramo"})
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            res = self._lookup()
        self.assertEqual(res["status"], "not_in_odoo")

    def test_lookup_phone_only_is_not_enough(self):
        self.env["res.partner"].create({"name": "Otra Persona", "phone": "5512345678"})
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            res = self._lookup()
        self.assertEqual(res["status"], "not_in_odoo")

    def test_lookup_email_wildcards_are_literal(self):
        """`_` del correo no es comodín: pedroXexample no es pedro_example."""
        payload = {"success": True, "data": dict(LUYOA_CUSTOMER["data"], email="pedro_p@example.com")}
        self.env["res.partner"].create({"name": "Otro", "email": "pedroXp@example.com"})
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, payload)
            res = self._lookup()
        self.assertEqual(res["status"], "not_in_odoo")

    def test_lookup_uid_conflict(self):
        """El contacto con el mismo correo ya está ligado a OTRA tarjeta: no
        se asigna ni se crea."""
        self.env["res.partner"].create({
            "name": "Pedro Páramo",
            "email": "pedro@example.com",
            "luyoa_customer_uid": "OtraTarjeta-0000000001",
        })
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            res = self._lookup()
            self.assertEqual(res["status"], "uid_conflict")
            self.assertEqual(self._assign(action="assign")["status"], "uid_conflict")
            self.assertEqual(self._assign(action="create")["status"], "uid_conflict")

    def test_customer_uid_is_unique(self):
        self.env["res.partner"].create({"name": "Uno", "luyoa_customer_uid": TEST_UID})
        with self.assertRaises(psycopg2.IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env["res.partner"].create({"name": "Dos", "luyoa_customer_uid": TEST_UID})

    def test_lookup_not_in_odoo(self):
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            res = self._lookup()
        self.assertEqual(res["status"], "not_in_odoo")
        self.assertFalse(res["partner"])
        self.assertEqual(res["luyoa"]["first_name"], "Pedro")

    def test_lookup_ambiguous(self):
        self.env["res.partner"].create({"name": "Pedro Páramo", "phone": "5512345678"})
        self.env["res.partner"].create({"name": "Pedro Páramo", "phone": "5512345678"})
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            res = self._lookup()
        self.assertEqual(res["status"], "ambiguous")
        self.assertEqual(len(res["candidates"]), 2)

    def test_lookup_customer_not_found(self):
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, {"success": False, "error": "Customer not found"}, status_code=404)
            res = self._lookup()
        self.assertEqual(res["status"], "customer_not_found")

    def test_lookup_unauthorized(self):
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, {"success": False, "error": "Unauthorized"}, status_code=401)
            res = self._lookup()
        self.assertEqual(res["status"], "unauthorized")
        # El cajero ve nuestro mensaje, no el texto en inglés de Luyoa.
        self.assertNotIn("Unauthorized", res["detail"])
        self.assertIn("administrador", res["detail"])

    def test_lookup_forbidden(self):
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, {"success": False, "error": "Forbidden"}, status_code=403)
            res = self._lookup()
        self.assertEqual(res["status"], "forbidden")

    def test_lookup_connection_error(self):
        with patch("%s.requests.get" % MODULE, side_effect=requests.Timeout):
            res = self._lookup()
        self.assertEqual(res["status"], "connection_error")

    def test_lookup_sends_auth_headers(self):
        """Las tres credenciales viajan en cada consulta."""
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            self._lookup()
        _url, kwargs = mock_get.call_args
        headers = kwargs["headers"]
        self.assertEqual(headers["X-Integration-UID"], "int-uid-test")
        self.assertEqual(headers["X-Business-UID"], "biz-uid-test")
        self.assertEqual(headers["Authorization"], "Bearer token-test")
        self.assertEqual(kwargs["timeout"], 15)

    def test_integration_uid_required(self):
        """Sin Integration UID hay config_error: la API responde 401 sin él
        (validado contra el entorno real)."""
        self.config.luyoa_integration_uid = False
        res = self._lookup()
        self.assertEqual(res["status"], "config_error")
        self.assertIn("Integration UID", res["detail"])

    def test_lookup_by_uid_match(self):
        """El UID guardado en el partner gana sobre correo/teléfono/nombre."""
        self.env["res.partner"].create({
            "name": "Otro Nombre",
            "luyoa_customer_uid": TEST_UID,
        })
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            res = self._lookup()
        self.assertEqual(res["status"], "found")
        self.assertEqual(res["match_by"], "uid")

    def test_lookup_archived_partner(self):
        partner = self.env["res.partner"].create({
            "name": "Pedro Páramo",
            "email": "pedro@example.com",
        })
        partner.action_archive()
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            res = self._lookup()
        self.assertEqual(res["status"], "archived")

    # ── Assign (escritura) ────────────────────────────────────────────────────

    def test_assign_found(self):
        partner = self.env["res.partner"].create({
            "name": "Pedro Páramo",
            "email": "pedro@example.com",
        })
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            res = self._assign(action="assign")
        self.assertEqual(res["status"], "assigned")
        self.assertEqual(res["partner_id"], partner.id)
        # Backfill del UID: matcheó por correo, se guarda el UID de Luyoa.
        self.assertEqual(partner.luyoa_customer_uid, TEST_UID)

    def test_assign_uid_backfill_is_idempotent(self):
        partner = self.env["res.partner"].create({
            "name": "Pedro Páramo",
            "email": "pedro@example.com",
            "luyoa_customer_uid": TEST_UID,
        })
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            res = self._assign(action="assign")
        self.assertEqual(res["status"], "assigned")
        self.assertEqual(partner.luyoa_customer_uid, TEST_UID)

    def test_create_partner(self):
        count_before = self.env["res.partner"].search_count([])
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            res = self._assign(action="create")
        self.assertEqual(res["status"], "created")
        partner = self.env["res.partner"].browse(res["partner_id"])
        self.assertEqual(partner.name, "Pedro Páramo")
        self.assertEqual(partner.email, "pedro@example.com")
        self.assertEqual(partner.phone, "5512345678")
        self.assertEqual(partner.luyoa_customer_uid, TEST_UID)
        self.assertEqual(self.env["res.partner"].search_count([]), count_before + 1)

    def test_create_does_not_duplicate(self):
        """Si el contacto apareció entre la fase 1 y la confirmación, create
        asigna en vez de duplicar."""
        partner = self.env["res.partner"].create({
            "name": "Pedro Páramo",
            "email": "pedro@example.com",
        })
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, LUYOA_CUSTOMER)
            res = self._assign(action="create")
        self.assertEqual(res["status"], "assigned")
        self.assertEqual(res["partner_id"], partner.id)

    def test_create_without_name_fails(self):
        """Ficha de Luyoa sin nombre: se rechaza antes de buscar o crear."""
        payload = {
            "success": True,
            "data": {"firstName": "", "lastName": "", "email": "x@example.com"},
        }
        count_before = self.env["res.partner"].search_count([])
        with patch("%s.requests.get" % MODULE) as mock_get:
            self._mock(mock_get, payload)
            res = self._assign(action="create")
        self.assertEqual(res["status"], "unexpected_response")
        self.assertIn("nombre", res["detail"])
        self.assertEqual(self.env["res.partner"].search_count([]), count_before)
