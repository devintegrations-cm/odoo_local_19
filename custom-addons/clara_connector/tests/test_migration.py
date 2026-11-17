# -*- coding: utf-8 -*-
"""The 2.0.0 migration: the crons and parameters of the order flow go, the users of the old groups join the new
ones, cards and transactions are kept and rewritten from their own payload without the card number. The 2.0.1
migration: the national id columns of earlier versions leave the transactions table, and nothing else."""
import importlib.util
import json
import os

from odoo import release
from odoo.tools.sql import column_exists

from .common import HOLDER, HOLDER_EMAIL, MASKED_PAN, ClaraCase, card_payload, transaction_payload

MIGRATIONS = os.path.join(os.path.dirname(__file__), "..", "migrations")
NATIONAL_ID_COLUMNS = (("clara_transaction", "cardholder_vat"), ("clara_transaction", "receipt_issuer_vat"))


def load(version, name):
    """The migration script ``name`` of module version ``version`` (the folder of this Odoo series: 17.0.x or 19.0.x)."""
    path = os.path.join(MIGRATIONS, "%s.%s" % (release.series, version), name + ".py")
    spec = importlib.util.spec_from_file_location("clara_connector_migration_%s_%s" % (version.replace(".", "_"), name.replace("-", "_")), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMigration(ClaraCase):
    def _xmlid(self, module, name, record):
        self.env["ir.model.data"].create({"module": module, "name": name, "model": record._name, "res_id": record.id})

    def _columns(self, table):
        self.env.cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table,))
        return {row[0] for row in self.env.cr.fetchall()}

    def _add_national_id_columns(self):
        """The columns a database of versions before 2.0.0 has (a fresh one has none of them)."""
        for table, column in NATIONAL_ID_COLUMNS:
            self.assertFalse(column_exists(self.env.cr, table, column), "%s.%s exists on a fresh database" % (table, column))
            self.assertNotIn(column, self.Transaction._fields)
            self.env.cr.execute("ALTER TABLE %s ADD COLUMN %s varchar" % (table, column))

    def test_migration_cleans_the_order_flow_and_keeps_the_data(self):
        Cron = self.env["ir.cron"]
        model = self.env["ir.model"]._get("clara.transaction")
        old_crons = {}
        for name in ("ir_cron_clara_sync_transactions", "ir_cron_clara_sync_cards", "ir_cron_clara_process_orders", "ir_cron_clara_weekly_run"):
            old_crons[name] = Cron.create({"name": name, "model_id": model.id, "state": "code", "code": "model._cron_process_orders()", "active": False})
            self._xmlid("clara_connector", name, old_crons[name])
        for key, value in (("clara_connector.auto_create_orders", "True"), ("clara_connector.anthropic_api_key", "sk-test"), ("clara_connector.schedule_mode", "weekly"),
                           ("clara_connector.clara_sync_from_date", "2026-10-19"), ("clara_purchase_bridge.reviewer_user_id", "")):
            self.icp.set_param(key, value)
        old_user_group = self.env["res.groups"].create({"name": "Clara User"})
        old_manager_group = self.env["res.groups"].create({"name": "Clara Manager"})
        self._xmlid("clara_connector", "group_clara_user", old_user_group)
        self._xmlid("clara_connector", "group_clara_manager", old_manager_group)
        groups_field = "group_ids" if "group_ids" in self.env["res.users"]._fields else "groups_id"   # renamed in Odoo 19
        reader = self.env["res.users"].create({"name": "Antiguo lector", "login": "antiguo.lector@test.local", groups_field: [(6, 0, [self.env.ref("base.group_user").id, old_user_group.id])]})
        manager = self.env["res.users"].create({"name": "Antiguo gestor", "login": "antiguo.gestor@test.local", groups_field: [(6, 0, [self.env.ref("base.group_user").id, old_manager_group.id])]})
        # data of earlier versions: a card that kept Clara's payload (card number included), a transaction with it
        order = self._order("P77201")
        card = self.Card.create({"clara_uuid": "card-old", "cardholder_name": "x"})
        self.env.cr.execute("ALTER TABLE clara_card ADD COLUMN IF NOT EXISTS raw_payload text")
        self.env.cr.execute("UPDATE clara_card SET raw_payload = %s WHERE id = %s", (json.dumps(card_payload("card-old", status="MASTER_LOCKED", lock="MASTER_LOCKED", card_type="MASTER_VIRTUAL")), card.id))
        tx = self.Transaction.create({"clara_uuid": "tx-old", "raw_payload": json.dumps(transaction_payload("tx-old", comment="P77201\nPaquete Salitre")), "cardholder_name": "x"})
        self.assertIn(MASKED_PAN, tx.raw_payload)
        self._add_national_id_columns()
        self.env.cr.execute("UPDATE clara_transaction SET cardholder_vat = '1020304050', receipt_issuer_vat = '900714035' WHERE id = %s", (tx.id,))
        weekly = self.env.ref("clara_connector.ir_cron_clara_weekly_sync")
        before = self.Transaction.search_count([]), self.Card.search_count([]), self.Order.search_count([])

        # as Odoo runs them on an update from 1.x: every pre-migration, the module's data, then every post-migration in order
        old_version = release.series + ".1.0.9"
        load("2.0.0", "pre-migrate").migrate(self.env.cr, old_version)
        load("2.0.0", "post-migrate").migrate(self.env.cr, old_version)
        load("2.0.1", "post-migrate").migrate(self.env.cr, old_version)
        self.env.invalidate_all()

        self.assertFalse(self.env["ir.cron"].with_context(active_test=False).browse([c.id for c in old_crons.values()]).exists())
        self.assertTrue(weekly.exists() and weekly.active)
        for key in ("clara_connector.auto_create_orders", "clara_connector.anthropic_api_key", "clara_connector.schedule_mode", "clara_connector.clara_sync_from_date", "clara_purchase_bridge.reviewer_user_id"):
            self.assertFalse(self.icp.get_param(key), key)
        self.assertEqual(self.icp.get_param("clara_connector.last_sync_date"), "2026-10-19")
        self.assertTrue(reader.has_group("clara_purchase_bridge.group_clara_reader"))
        self.assertFalse(reader.has_group("clara_purchase_bridge.group_clara_admin"))
        self.assertTrue(manager.has_group("clara_purchase_bridge.group_clara_admin"))
        self.assertFalse((old_user_group | old_manager_group).exists())
        self.assertEqual((self.Transaction.search_count([]), self.Card.search_count([]), self.Order.search_count([])), before)
        self.assertEqual((card.status, card.card_type, card.last_four, card.cardholder_email), ("blocked", "virtual", "5458", HOLDER_EMAIL))
        self.env.cr.execute("SELECT raw_payload FROM clara_card WHERE id = %s", (card.id,))
        self.assertIsNone(self.env.cr.fetchone()[0])
        self.assertNotIn(MASKED_PAN, tx.raw_payload)
        self.assertEqual((tx.cardholder_name, tx.clara_comment, tx.purchase_order_id, tx.reconciliation_state, tx.name), (HOLDER, "P77201\nPaquete Salitre", order, "reconciled", "Uber · 2026-10-08"))
        self.assertEqual(order.state, "draft")
        for table, column in NATIONAL_ID_COLUMNS:
            self.assertFalse(column_exists(self.env.cr, table, column), "%s.%s survived the migration" % (table, column))
        self.assertNotIn("1020304050", tx.raw_payload)

    def test_national_id_columns_are_dropped_and_nothing_else(self):
        cr = self.env.cr
        self._add_national_id_columns()
        before = self._columns("clara_transaction")

        load("2.0.1", "post-migrate").migrate(cr, release.series + ".2.0.0")

        dropped = {column for _, column in NATIONAL_ID_COLUMNS}
        for table, column in NATIONAL_ID_COLUMNS:
            self.assertFalse(column_exists(cr, table, column), "%s.%s survived the migration" % (table, column))
        self.assertEqual(self._columns("clara_transaction"), before - dropped)
        # a database that never had the columns, or already lost them, is left alone
        load("2.0.1", "post-migrate").migrate(cr, release.series + ".2.0.1")
        self.assertEqual(self._columns("clara_transaction"), before - dropped)
