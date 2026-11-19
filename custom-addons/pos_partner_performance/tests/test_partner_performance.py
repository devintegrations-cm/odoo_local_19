from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import fields
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestPartnerPerformance(TransactionCase):
    """Frequent customers ranked per point of sale and over the last N days."""

    LIMIT = 3

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("point_of_sale.limited_customer_count", cls.LIMIT)
        cls.config_a = cls.env["pos.config"].create({"name": "Tienda A (test)"})
        cls.config_b = cls.env["pos.config"].create({"name": "Tienda B (test)"})
        cls.session_a = cls.env["pos.session"].create({"config_id": cls.config_a.id, "user_id": cls.env.uid})
        cls.session_b = cls.env["pos.session"].create({"config_id": cls.config_b.id, "user_id": cls.env.uid})
        # names starting with "0" so they would sort first by name: only the order count may push them down
        cls.local = cls.env["res.partner"].create({"name": "0 Cliente de la tienda A"})
        cls.other_store = cls.env["res.partner"].create({"name": "0 Cliente de la tienda B"})
        cls.old = cls.env["res.partner"].create({"name": "0 Cliente antiguo de la tienda A"})
        cls.default_customer = cls.env["res.partner"].create({"name": "zz Venta mostrador (test)"})

    def _order(self, session, partner, days_ago=0):
        order = self.env["pos.order"].create({
            "session_id": session.id,
            "partner_id": partner.id,
            "amount_tax": 0.0,
            "amount_total": 0.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
        })
        if days_ago:
            order.date_order = fields.Datetime.now() - timedelta(days=days_ago)
        return order

    def _loaded(self, config, offset=0):
        return [row[0] for row in config.get_limited_partners_loading(offset)]

    def test_new_point_of_sale_has_it_enabled_with_90_days(self):
        self.assertTrue(self.config_a.frequent_partners_by_store)
        self.assertEqual(self.config_a.frequent_partners_days, 90)

    def test_ranking_counts_only_the_orders_of_this_point_of_sale(self):
        for _ in range(3):
            self._order(self.session_b, self.other_store)
        self._order(self.session_a, self.local)
        self.assertEqual(self._loaded(self.config_a)[0], self.local.id)
        self.assertEqual(self._loaded(self.config_b)[0], self.other_store.id)

    def test_orders_older_than_the_window_do_not_count(self):
        self.config_a.frequent_partners_days = 30
        for _ in range(5):
            self._order(self.session_a, self.old, days_ago=60)
        self._order(self.session_a, self.local)
        # with every order counted, the old customer (5 orders) would come first
        self.assertEqual(self._loaded(self.config_a)[0], self.local.id)

    def test_same_limit_and_pagination_as_standard(self):
        first = self._loaded(self.config_a)
        second = self._loaded(self.config_a, offset=self.LIMIT)
        self.assertEqual(len(first), self.LIMIT)
        self.assertEqual(len(second), self.LIMIT)
        self.assertFalse(set(first) & set(second), "the next page brings other customers")

    def test_default_customer_only_on_the_first_page(self):
        self.config_a.pos_customer_id = self.default_customer
        first = self._loaded(self.config_a)
        second = self._loaded(self.config_a, offset=self.LIMIT)
        self.assertIn(self.default_customer.id, first, "loaded when the POS opens")
        # on later pages it would make the page limit + 1 long and the POS would skip one customer
        self.assertNotIn(self.default_customer.id, second)
        self.assertEqual(len(second), self.LIMIT)

    def test_customers_of_another_company_are_not_loaded(self):
        other_company = self.env["res.company"].create({"name": "Otra compañía (test)"})
        foreign = self.env["res.partner"].create({"name": "0 0 Cliente de otra compañía", "company_id": other_company.id})
        # by name it would be the first one of the list
        self.assertNotIn(foreign.id, self._loaded(self.config_a))

    def test_disabled_falls_back_to_the_standard_ranking(self):
        self.config_a.frequent_partners_by_store = False
        for _ in range(3):
            self._order(self.session_b, self.other_store)
        # standard Odoo counts the orders of every store: the customer of store B leads in store A too
        self.assertEqual(self._loaded(self.config_a)[0], self.other_store.id)

    def test_zero_days_falls_back_to_the_standard_ranking(self):
        self.config_a.frequent_partners_days = 0
        for _ in range(3):
            self._order(self.session_b, self.other_store)
        self.assertEqual(self._loaded(self.config_a)[0], self.other_store.id)

    def test_negative_days_are_rejected(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.config_a.frequent_partners_days = -1
            self.config_a.flush_recordset()
