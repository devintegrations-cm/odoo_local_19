# -*- coding: utf-8 -*-
"""The weekly sync: as few requests as possible (only what Clara created or updated since the last sync, pages of
the maximum size, only changed records written), the cards without the card number, the links with the cardholder
table, the single cron and «Sincronizar ahora» for administrators only."""
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError

from ..services import clara_api_service as svc
from odoo.tools import mute_logger

from .common import HOLDER, HOLDER_EMAIL, HOLDER_UUID, MASKED_PAN, ClaraCase, FakeResponse, card_payload, fake_http, transaction_payload


class TestSync(ClaraCase):
    def test_first_sync_by_operation_date_then_only_changes_since_the_last_sync(self):
        self.icp.set_param("clara_connector.sync_start_date", "2026-09-01 05:00:00")
        self.icp.set_param("clara_connector.sync_overlap_days", "2")
        first = transaction_payload("tx-1", comment="P00001")
        with self.api(transactions=[first]) as windows:
            log = self.Transaction._run_sync("cron")
        self.assertEqual(windows, [{"from_date": fields.Date.from_string("2026-09-01")}])
        self.assertEqual((log.state, log.records_fetched, log.records_created, log.records_updated, log.records_skipped), ("success", 1, 1, 0, 0))
        today = self.Transaction._today_local()
        self.assertEqual(self.icp.get_param("clara_connector.last_sync_date"), fields.Date.to_string(today))
        tx = self.Transaction.search([("clara_uuid", "=", "tx-1")])
        tx.last_sync_date = fields.Datetime.now() - timedelta(days=30)
        first_sync = tx.last_sync_date
        # second run: only what changed since the last sync, minus the overlap; an unchanged record is not written
        self.icp.set_param("clara_connector.last_sync_date", "2026-10-26")
        changed = transaction_payload("tx-1", comment="P00001", legalization="Rejected", last_update="2026-10-27")
        with self.api(transactions=[first, changed, transaction_payload("tx-2")]) as windows:
            log = self.Transaction._run_sync("cron")
        self.assertEqual(windows, [{"updated_since": fields.Date.from_string("2026-10-24")}])
        self.assertEqual((log.records_fetched, log.records_created, log.records_updated, log.records_skipped, log.records_errored), (3, 1, 1, 1, 0))
        self.assertEqual((tx.approval_status, tx.reconciliation_state), ("Rejected", "rejected"))
        self.assertNotEqual(tx.last_sync_date, first_sync)
        # a failed record keeps the last sync date where it was, so the window is read again next time
        self.icp.set_param("clara_connector.last_sync_date", "2026-10-26")
        broken = transaction_payload("tx-3")
        broken["amountValue"] = {"amount": "not-a-number", "currency": "COP"}
        with self.api(transactions=[broken]):
            log = self.Transaction._run_sync("cron")
        self.assertEqual((log.state, log.records_errored), ("partial", 1))
        self.assertEqual(self.icp.get_param("clara_connector.last_sync_date"), "2026-10-26")

    def test_pages_of_the_maximum_size_and_one_call_per_page(self):
        self.icp.set_param("clara_connector.page_size", "100")
        transactions = [transaction_payload("tx-%03d" % n) for n in range(250)]
        with self.http(transactions=transactions, cards=[card_payload("card-%s" % n) for n in range(29)]) as calls:
            result = self.Transaction._run_weekly_sync("cron")
        gets = [c for c in calls if c["method"] == "GET"]
        self.assertEqual([c["params"]["size"] for c in gets], [100] * 4)
        self.assertEqual([c["params"]["page"] for c in gets if "/transactions" in c["url"]], [0, 1, 2])   # 250 records: three pages, the last one short
        self.assertEqual([c["params"]["page"] for c in gets if "/cards" in c["url"]], [0])                # 29 cards: one call
        self.assertEqual((result["transactions"].api_calls, result["cards"].api_calls), (3, 1))
        self.assertEqual((self.Transaction.search_count([("clara_uuid", "like", "tx-")]), self.Card.search_count([("clara_uuid", "like", "card-")])), (250, 29))
        # a size above the API's maximum is capped
        self.icp.set_param("clara_connector.page_size", "500")
        self.assertEqual(svc.ClaraAPIService.page_size_param(self.env), 100)
        self.icp.set_param("clara_connector.page_size", "abc")
        self.assertEqual(svc.ClaraAPIService.page_size_param(self.env), 100)

    def test_pages_answered_as_a_bare_list_or_without_page_metadata(self):
        """Clara's ``last`` and ``totalPages`` are read only from a page object. A bare list says nothing about the
        next page: a full one is followed by the next page and an empty one ends the read. A page object without
        those keys (or with ``meta`` null) ends at the short page."""
        self.icp.set_param("clara_connector.page_size", "2")
        items = [transaction_payload("tx-%s" % n) for n in range(4)]
        shapes = {"list": lambda chunk: chunk, "bare_dict": lambda chunk: {"content": chunk, "meta": None}}
        for shape, wrap in shapes.items():
            pages = []

            def request(method, url, headers=None, params=None, **kwargs):
                page, size = int(params["page"]), int(params["size"])
                pages.append(page)
                return FakeResponse(wrap(items[page * size:(page + 1) * size]), url=url)

            _, post, _ = fake_http()
            with patch.object(svc.requests, "request", request), patch.object(svc.requests, "post", post):
                result = svc.ClaraAPIService(self.env).get_transactions()
            self.assertEqual([tx["uuid"] for tx in result], ["tx-0", "tx-1", "tx-2", "tx-3"], shape)
            self.assertEqual(pages, [0, 1, 2], shape)   # two full pages, then the empty one that ends the read

    def test_cards_keep_no_card_number_and_take_area_and_cost_centre_from_the_table(self):
        plan = self.env["account.analytic.plan"].create({"name": "Test plan"})
        account = self.env["account.analytic.account"].create({"name": "[TINS] Institucional Test - Empresa Test", "plan_id": plan.id})
        self.Rule.create({"name": HOLDER, "cardholder_email": HOLDER_EMAIL, "area": "COMERCIAL", "analytic_distribution": {str(account.id): 100.0}})
        cards = [
            card_payload("card-active"),
            card_payload("card-locked", status="MASTER_LOCKED", lock="MASTER_LOCKED", card_type="MASTER_VIRTUAL", alias="Clara Virtual"),
            card_payload("card-lock-code", status="ACTIVE", lock="LOCKED_BY_USER"),
            card_payload("card-inactive", status="INACTIVE", holder="OTRO TITULAR PRUEBA", email="otro.titular@test.local", holder_uuid="uuid-titular-prueba-0002"),
            card_payload("card-cancelled", status="CANCELLED", periodicity="WEEKLY"),
            card_payload("card-pending", status="PENDING"),
        ]
        with self.api(cards=cards):
            log = self.Card._run_card_sync("cron")
        self.assertEqual((log.state, log.records_created), ("success", 6))
        by_uuid = {c.clara_uuid: c for c in self.Card.search([("clara_uuid", "like", "card-")])}
        self.assertEqual({k: v.status for k, v in by_uuid.items()}, {"card-active": "active", "card-locked": "blocked", "card-lock-code": "blocked", "card-inactive": "inactive", "card-cancelled": "cancelled", "card-pending": "inactive"})
        self.assertEqual((by_uuid["card-active"].card_type, by_uuid["card-locked"].card_type), ("physical", "virtual"))
        self.assertEqual((by_uuid["card-active"].monthly_limit, by_uuid["card-cancelled"].monthly_limit, by_uuid["card-cancelled"].periodicity), (2000000.0, 0.0, "WEEKLY"))
        self.assertEqual((by_uuid["card-active"].last_four, by_uuid["card-active"].name, by_uuid["card-locked"].status_raw), ("5458", HOLDER + " · 5458", "MASTER_LOCKED / MASTER_LOCKED"))
        self.assertEqual((by_uuid["card-active"].area, by_uuid["card-active"].analytic_account_id, by_uuid["card-inactive"].area), ("COMERCIAL", account, False))
        self.assertNotIn("raw_payload", self.Card._fields)
        for card in by_uuid.values():
            for name, field in self.Card._fields.items():
                value = card[name]
                if isinstance(value, str):
                    self.assertNotIn(MASKED_PAN[:6], value, name)
        # an unchanged card is not written again; a changed one is
        with self.api(cards=cards):
            log = self.Card._run_card_sync("cron")
        self.assertEqual((log.records_created, log.records_updated, log.records_skipped), (0, 0, 6))
        cards[0]["lockCode"] = "LOCKED"
        with self.api(cards=cards):
            log = self.Card._run_card_sync("cron")
        self.assertEqual((log.records_updated, log.records_skipped, by_uuid["card-active"].status), (1, 5, "blocked"))

    def test_links_follow_the_cardholder_table_and_the_cards(self):
        with self.api(transactions=[transaction_payload("tx-1")], cards=[card_payload("card-1")]):
            self.Transaction._run_weekly_sync("cron")
        tx = self.Transaction.search([("clara_uuid", "=", "tx-1")])
        card = self.Card.search([("clara_uuid", "=", "card-1")])
        self.assertEqual((tx.card_id, tx.area, card.area), (card, False, False))
        plan = self.env["account.analytic.plan"].create({"name": "Test plan"})
        account = self.env["account.analytic.account"].create({"name": "[TINS] Institucional Test - Empresa Test", "plan_id": plan.id})
        # a cardholder rule without account defers to its area's rule (the seeded table has one for COMERCIAL)
        rule = self.Rule.create({"name": HOLDER, "cardholder_uuid": HOLDER_UUID, "area": "COMERCIAL"})
        self.assertEqual((tx.analytic_rule_id.kind, tx.analytic_rule_id.area, tx.area, card.area), ("area", "COMERCIAL", "COMERCIAL", "COMERCIAL"))
        rule.analytic_distribution = {str(account.id): 100.0}
        self.assertEqual((tx.analytic_rule_id, tx.area, tx.analytic_account_id, card.analytic_rule_id, card.area, card.analytic_account_id), (rule, "COMERCIAL", account, rule, "COMERCIAL", account))
        rule.area = "MERCADEO"
        self.assertEqual((tx.area, card.area), ("MERCADEO", "MERCADEO"))
        rule.unlink()
        self.assertEqual((tx.analytic_rule_id.id, tx.area, tx.analytic_account_id.id, card.area), (False, False, False, False))
        self.assertEqual(card.transaction_count, 1)
        self.assertEqual(card.action_open_transactions()["domain"], [("card_id", "=", card.id)])

    def test_only_administrators_sync_now(self):
        reader = self._user("clara_purchase_bridge.group_clara_reader", "lectura2@test.local")
        admin = self._user("clara_purchase_bridge.group_clara_admin", "admin2@test.local")
        with self.api(transactions=[transaction_payload("tx-1")], cards=[card_payload("card-1")]):
            with self.assertRaises(AccessError):
                self.Transaction.with_user(reader).action_sync_now()
            action = self.Transaction.with_user(admin).action_sync_now()
        self.assertEqual((action["tag"], action["params"]["type"], action["params"]["next"]["tag"]), ("display_notification", "success", "reload"))
        self.assertIn("1 nuevas", action["params"]["message"])
        logs = self.env["clara.sync.log"].search([("triggered_by", "=", "manual")])
        self.assertEqual(sorted(logs.mapped("sync_type")), ["cards", "transactions"])
        # a failure is said, not hidden
        self.env.company.clara_tax_identifier = False
        with mute_logger("odoo.addons.clara_connector.models.clara_transaction", "odoo.addons.clara_connector.models.clara_card"):
            action = self.Transaction.with_user(admin).action_sync_now()
        self.assertEqual((action["params"]["type"], action["params"]["sticky"]), ("danger", True))
        self.assertIn("NIT", action["params"]["message"])
        # the button exists for administrators only, on both lists and in the settings
        for view in ("view_clara_transaction_tree", "view_clara_card_tree"):
            arch = self.env.ref("clara_connector." + view).arch
            self.assertIn('name="action_sync_now"', arch)
            self.assertIn('groups="clara_purchase_bridge.group_clara_admin"', arch)
        settings = self.env["res.config.settings"].with_user(self.env.ref("base.user_admin")).create({})
        self.assertEqual(settings.clara_page_size, 100)
        with self.api(transactions=[], cards=[]):
            self.assertEqual(settings.action_clara_sync_now()["tag"], "display_notification")

    def test_one_weekly_cron_on_sunday_night_in_bogota(self):
        cron = self.env.ref("clara_connector.ir_cron_clara_weekly_sync")
        clara_crons = self.env["ir.cron"].with_context(active_test=False).search([("model_id.model", "in", ("clara.transaction", "clara.card", "clara.sync.log"))])
        self.assertEqual(clara_crons, cron)
        self.assertEqual((cron.active, cron.interval_number, cron.interval_type), (True, 1, "weeks"))
        self.assertIn("_cron_weekly_sync", cron.code)
        self.assertEqual((cron.nextcall.weekday(), cron.nextcall.hour, cron.nextcall.minute), (0, 3, 0))   # Monday 03:00 UTC = Sunday 22:00 America/Bogota
        self.assertGreater(cron.nextcall, fields.Datetime.now())
        self.assertLessEqual(cron.nextcall - fields.Datetime.now(), timedelta(days=7))
