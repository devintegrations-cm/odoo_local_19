"""The 2.0.1 migration: the national id columns of earlier versions leave the purchase order and the cardholder
table, and nothing else in those tables is touched."""
import importlib.util
import os

from odoo import release
from odoo.tests import TransactionCase, tagged
from odoo.tools.sql import column_exists

MIGRATIONS = os.path.join(os.path.dirname(__file__), "..", "migrations")
NATIONAL_ID_COLUMNS = (("purchase_order", "clara_cardholder_vat"), ("clara_analytic_rule", "cardholder_vat"), ("clara_analytic_rule", "vat_key"))


def load(version, name):
    """The migration script ``name`` of module version ``version`` (the folder of this Odoo series: 17.0.x or 19.0.x)."""
    path = os.path.join(MIGRATIONS, "%s.%s" % (release.series, version), name + ".py")
    spec = importlib.util.spec_from_file_location("clara_purchase_bridge_migration_%s_%s" % (version.replace(".", "_"), name.replace("-", "_")), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install")
class TestMigration(TransactionCase):
    def _columns(self, table):
        self.env.cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table,))
        return {row[0] for row in self.env.cr.fetchall()}

    def test_national_id_columns_are_dropped_and_nothing_else(self):
        cr = self.env.cr
        for table, column in NATIONAL_ID_COLUMNS:
            self.assertFalse(column_exists(cr, table, column), "%s.%s exists on a fresh database" % (table, column))
            self.assertNotIn(column, self.env[self.env["ir.model"]._get(table.replace("_", "."))._name]._fields)
            cr.execute('ALTER TABLE %s ADD COLUMN %s varchar' % (table, column))   # as a database of versions before 2.0.0 has them
        before = {table: self._columns(table) for table, _ in NATIONAL_ID_COLUMNS}

        load("2.0.1", "post-migrate").migrate(cr, release.series + ".2.0.0")

        for table, column in NATIONAL_ID_COLUMNS:
            self.assertFalse(column_exists(cr, table, column), "%s.%s survived the migration" % (table, column))
        for table, columns in before.items():
            dropped = {column for t, column in NATIONAL_ID_COLUMNS if t == table}
            self.assertEqual(self._columns(table), columns - dropped, table)
        # a database that never had the columns, or already lost them, is left alone
        load("2.0.1", "post-migrate").migrate(cr, release.series + ".2.0.1")
        for table, columns in before.items():
            self.assertEqual(self._columns(table), columns - {column for t, column in NATIONAL_ID_COLUMNS if t == table}, table)
