# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDeleteOrderAccess(TransactionCase):
    """Configuration of the "who may delete orders" rule.

    The rule itself is applied in the interface (beforeDeleteOrder); what is
    checked here is that the settings screen stores the list on the point of
    sale, and that an empty list still means "everyone", which is the behaviour
    in production today.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.journal = cls.env["account.journal"].create({
            "name": "Cash Delete Order Test",
            "type": "cash",
            "code": "CDLO",
            "company_id": cls.company.id,
        })
        cls.payment_method = cls.env["pos.payment.method"].create({
            "name": "Cash Delete Order Test",
            "journal_id": cls.journal.id,
            "is_cash_count": True,
            "split_transactions": False,
        })
        cls.pos_config = cls.env["pos.config"].create({
            "name": "Test POS Delete Order",
            "module_pos_restaurant": False,
            "journal_id": cls.journal.id,
            "payment_method_ids": [(6, 0, [cls.payment_method.id])],
        })
        cls.employee = cls.env["hr.employee"].create({
            "name": "Empleado Prueba",
            "company_id": cls.company.id,
        })

    def test_empty_list_is_the_default(self):
        self.assertFalse(self.pos_config.able_del_employee_ids)

    def test_settings_write_the_list_through_to_pos_config(self):
        settings = self.env["res.config.settings"].create({
            "pos_config_id": self.pos_config.id,
        })
        settings.pos_del_able_employee_ids = [(6, 0, [self.employee.id])]
        settings.execute()

        self.assertEqual(self.pos_config.able_del_employee_ids, self.employee)

    def test_related_is_not_untouchable(self):
        """readonly=False: the settings screen must be able to store the value."""
        settings = self.env["res.config.settings"].create({
            "pos_config_id": self.pos_config.id,
        })

        self.assertTrue(settings._fields["pos_del_able_employee_ids"].related)
        self.assertFalse(settings._fields["pos_del_able_employee_ids"].readonly)
