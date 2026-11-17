# -*- coding: utf-8 -*-
"""What makes the modules read-only: no method of either module creates, confirms or writes a purchase order, and no
call to Clara uses anything but GET."""
from unittest.mock import Mock, patch

from odoo.exceptions import AccessError, UserError

from ..services import clara_api_service as svc
from .common import HOLDER, HOLDER_UUID, ClaraCase, card_payload, transaction_payload

MODULES = ("clara_connector", "clara_purchase_bridge")
ADMIN_GROUP = "clara_purchase_bridge.group_clara_admin"


class TestReadOnly(ClaraCase):
    def test_no_method_of_the_modules_touches_purchase_orders(self):
        """Every path of the modules runs (both syncs, the links, the rule hooks, the manual sync) with the writing
        methods of purchase.order replaced by mocks: none is ever called. The connector adds nothing to purchase.order;
        the bridge adds only read-only fields (checked in its own tests)."""
        Order = self.Order
        self.assertFalse([cls for cls in type(Order).__mro__ if cls.__module__.startswith("odoo.addons.clara_connector")])
        for name in ("create_from_clara", "find_by_clara_uuid", "action_create_order", "_cron_process_orders"):
            self.assertFalse(hasattr(Order, name) or hasattr(self.Transaction, name), name)
        order = self._order("P77001")
        guards = {name: Mock(side_effect=AssertionError("purchase.order.%s was called" % name)) for name in ("create", "write", "unlink", "button_confirm", "button_cancel", "button_draft", "button_approve")}
        patches = [patch.object(type(Order), name, guard) for name, guard in guards.items()]
        for p in patches:
            p.start()
        try:
            transactions = [transaction_payload("tx-1", comment="P77001\nPaquete Salitre"), transaction_payload("tx-2", comment="", legalization="Needs Approval")]
            with self.api(transactions=transactions, cards=[card_payload("card-1")]):
                self.Transaction._cron_weekly_sync()
                self.Transaction.with_user(self.env.ref("base.user_admin")).action_sync_now()
            self.Rule.create({"name": HOLDER, "cardholder_uuid": HOLDER_UUID, "area": "COMERCIAL"})
            tx = self.Transaction.search([("clara_uuid", "=", "tx-1")])
            self.assertEqual((tx.purchase_order_id, tx.reconciliation_state), (order, "reconciled"))
            tx.action_open_order()
            self.Card.search([("clara_uuid", "=", "card-1")]).action_open_transactions()
        finally:
            for p in patches:
                p.stop()
        for name, guard in guards.items():
            self.assertFalse(guard.called, name)
        self.assertEqual(order.state, "draft")   # the order the test made is as the test made it

    def test_every_clara_call_is_a_get(self):
        """The real service code runs over a fake HTTP layer for a whole weekly run: every request to Clara is a GET;
        the only POST is the OAuth token. Any other method is refused before a request is built, and the service has
        no writing method left."""
        with self.http(transactions=[transaction_payload("tx-%s" % n) for n in range(3)], cards=[card_payload("card-1")]) as calls:
            self.Transaction._cron_weekly_sync()
            service = svc.ClaraAPIService(self.env)
            for method in ("POST", "PATCH", "PUT", "DELETE"):
                with self.assertRaises(UserError):
                    service._request(method, "/api/v3/transactions/labels/bulk", params={})
        methods = {c["method"] for c in calls if "/oauth/token" not in c["url"]}
        self.assertEqual(methods, {"GET"})
        self.assertEqual([c["url"].rsplit("/", 1)[1] for c in calls if c["method"] == "POST"], ["token"])
        self.assertEqual(self.env["clara.sync.log"].search([("state", "!=", "success")], limit=1).mapped("error_message"), [])
        for name in ("lock_card", "set_transaction_labels", "create_labels", "get_transaction_documents", "download_document", "get_labels", "_make_request"):
            self.assertFalse(hasattr(svc.ClaraAPIService, name), name)
        with self.assertRaises(UserError):
            svc.ClaraAPIService(self.env)._request("post", "/api/v3/cards")   # lower case does not slip through either

    def test_readers_read_everything_and_write_nothing(self):
        reader = self._user("clara_purchase_bridge.group_clara_reader", "lectura@test.local")
        with self.api(transactions=[transaction_payload("tx-1", comment="P77002")], cards=[card_payload("card-1")]):
            self.Transaction._cron_weekly_sync()
        tx = self.Transaction.search([("clara_uuid", "=", "tx-1")])
        card = self.Card.search([("clara_uuid", "=", "card-1")])
        log = self.env["clara.sync.log"].search([], limit=1)
        self.assertEqual(tx.with_user(reader).read(["purchase_order_id", "reconciliation_state", "cardholder_name"])[0]["cardholder_name"], HOLDER)
        self.assertEqual(card.with_user(reader).read(["status", "area"])[0]["status"], "active")
        self.assertTrue(log.with_user(reader).read(["state"]))
        self.assertEqual(self.Rule.with_user(reader).search_count([]) >= 0, True)
        for action in (lambda: tx.with_user(reader).write({"cardholder_name": "x"}), lambda: tx.with_user(reader).unlink(),
                       lambda: self.Transaction.with_user(reader).create({"clara_uuid": "new"}), lambda: card.with_user(reader).write({"status": "blocked"}),
                       lambda: self.Card.with_user(reader).create({"clara_uuid": "new-card"}), lambda: log.with_user(reader).unlink(),
                       lambda: self.Transaction.with_user(reader).action_sync_now()):
            with self.assertRaises(AccessError):
                action()
        for view in ("view_clara_transaction_tree", "view_clara_transaction_form", "view_clara_card_tree", "view_clara_card_form", "view_clara_card_kanban", "view_clara_sync_log_tree"):
            arch = self.env.ref("clara_connector." + view).arch
            self.assertTrue('create="false"' in arch and 'edit="false"' in arch and 'delete="false"' in arch, view)

    def test_credentials_are_read_by_administrators_only(self):
        """The Client ID, the Secret and the mTLS certificates of the company are fields of "Clara / Administrador":
        a reader gets AccessError on them (and only on them), on the company and on the settings. The API service
        reads them as superuser, so a sync works whoever triggers it."""
        reader = self._user("clara_purchase_bridge.group_clara_reader", "lectura3@test.local")
        admin = self._user("clara_purchase_bridge.group_clara_admin", "admin3@test.local")
        company = self.env.company
        self.assertEqual(company.with_user(reader).read(["name", "clara_country", "clara_tax_identifier"])[0]["clara_tax_identifier"], "900854410")
        for name in ("clara_client_id", "clara_client_secret", "clara_ca_cert", "clara_client_cert", "clara_client_key"):
            self.assertEqual(self.env["res.company"]._fields[name].groups, ADMIN_GROUP, name)
            self.assertEqual(self.env["res.config.settings"]._fields[name].groups, ADMIN_GROUP, name)
            with self.assertRaises(AccessError, msg=name):
                company.with_user(reader).read([name])
            with self.assertRaises(AccessError, msg=name):
                company.with_user(reader)[name]
        self.assertEqual(company.with_user(admin).read(["clara_client_id", "clara_client_secret"])[0]["clara_client_secret"], "secret-test")
        settings = self.env["res.config.settings"].with_user(self.env.ref("base.user_admin")).create({})   # settings pages are for system administrators
        self.assertEqual(settings.clara_client_secret, "secret-test")
        with self.assertRaises(AccessError):
            settings.with_user(reader).read(["clara_client_secret"])
        # the service reads the credentials whoever the user is: the cron (superuser) and the sync button (administrator)
        service = svc.ClaraAPIService(self.env(user=reader.id))
        self.assertEqual((service.client_id, service.client_secret, bool(service.client_cert), bool(service.client_key)), ("client-test", "secret-test", True, True))
