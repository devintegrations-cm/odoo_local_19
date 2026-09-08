# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestNumberCustomersConfig(TransactionCase):
    """Range configuration of the "ask the number of customers" prompt.

    The prompt itself lives in the interface; the important part here is that the
    accepted range is data and not a hardcoded number, and that a nonsensical
    range cannot be stored (a cashier cannot be asked for a negative number of
    guests, nor for a maximum below the minimum).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.journal = cls.env["account.journal"].create({
            "name": "Cash Number Customers Test",
            "type": "cash",
            "code": "CNCC",
            "company_id": cls.company.id,
        })
        cls.payment_method = cls.env["pos.payment.method"].create({
            "name": "Cash Number Customers Test",
            "journal_id": cls.journal.id,
            "is_cash_count": True,
            "split_transactions": False,
        })
        cls.pos_config = cls.env["pos.config"].create({
            "name": "Test POS Number Customers",
            "module_pos_restaurant": False,
            "journal_id": cls.journal.id,
            "payment_method_ids": [(6, 0, [cls.payment_method.id])],
        })

    def test_disabled_and_ranged_by_default(self):
        """Defaults keep the behaviour the stores have today: 1 to 20."""
        self.assertFalse(self.pos_config.enable_obligatory_ask_number_customers)
        self.assertEqual(self.pos_config.number_customers_min, 1)
        self.assertEqual(self.pos_config.number_customers_max, 20)

    def test_minimum_below_one_is_refused(self):
        with self.assertRaises(ValidationError):
            self.pos_config.number_customers_min = 0

    def test_maximum_below_minimum_is_refused(self):
        with self.assertRaises(ValidationError):
            self.pos_config.write({
                "number_customers_min": 10,
                "number_customers_max": 4,
            })

    def test_settings_write_range_through_to_pos_config(self):
        settings = self.env["res.config.settings"].create({
            "pos_config_id": self.pos_config.id,
        })
        settings.pos_enable_obligatory_ask_number_customers = True
        settings.pos_number_customers_min = 2
        settings.pos_number_customers_max = 8
        settings.execute()

        self.assertTrue(self.pos_config.enable_obligatory_ask_number_customers)
        self.assertEqual(self.pos_config.number_customers_min, 2)
        self.assertEqual(self.pos_config.number_customers_max, 8)

    def test_range_fields_are_prefixed_on_the_shared_settings_model(self):
        fields = self.env["res.config.settings"]._fields

        self.assertIn("pos_number_customers_min", fields)
        self.assertIn("pos_number_customers_max", fields)
        self.assertNotIn("number_customers_min", fields)
