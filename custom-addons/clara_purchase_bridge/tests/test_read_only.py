"""The bridge is read-only: no method of the module touches purchase orders, readers cannot write the cardholder
table and administrators can."""
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

MODULE = "clara_purchase_bridge"


@tagged("post_install", "-at_install")
class TestReadOnly(TransactionCase):
    def _user(self, group_xmlid, login):
        Users = self.env["res.users"]
        groups_field = "group_ids" if "group_ids" in Users._fields else "groups_id"   # renamed in Odoo 19
        return Users.create({"name": login, "login": login, groups_field: [(6, 0, [self.env.ref("base.group_user").id, self.env.ref(group_xmlid).id])]})

    def test_module_defines_no_method_on_purchase_order(self):
        """Only read-only fields (and the compute of one of them) are added to purchase.order."""
        Order = self.env["purchase.order"]
        classes = [cls for cls in type(Order).__mro__ if cls.__module__.startswith("odoo.addons." + MODULE + ".")]
        self.assertTrue(classes, "the bridge extends purchase.order with its read-only fields")
        for cls in classes:
            methods = sorted(name for name, value in vars(cls).items() if callable(value) and not name.startswith("__"))
            self.assertEqual(methods, ["_compute_clara_receipt_count"], cls)
        self.assertNotIn("create_from_clara", dir(Order))
        self.assertNotIn("find_by_clara_uuid", dir(Order))
        for name in Order._fields:
            if name.startswith("clara_"):
                self.assertTrue(Order._fields[name].readonly or Order._fields[name].compute, name)
        self.assertNotIn("clara_cardholder_vat", Order._fields)

    def test_reader_reads_and_admin_edits_the_cardholder_table(self):
        Rule = self.env["clara.analytic.rule"]
        reader = self._user("clara_purchase_bridge.group_clara_reader", "clara.reader@test.local")
        admin = self._user("clara_purchase_bridge.group_clara_admin", "clara.admin@test.local")
        rule = Rule.create({"name": "Titular Permisos Test", "area": "LEGAL"})
        self.assertEqual(Rule.with_user(reader).search([("id", "=", rule.id)]), rule)
        for action in (lambda: Rule.with_user(reader).create({"name": "Nadie", "area": "LEGAL"}),
                       lambda: rule.with_user(reader).write({"area": "IT"}),
                       lambda: rule.with_user(reader).unlink()):
            with self.assertRaises(AccessError):
                action()
        rule.with_user(admin).write({"area": "IT"})
        self.assertEqual(rule.area, "IT")
        self.assertTrue(admin.has_group("clara_purchase_bridge.group_clara_reader"))   # an administrator reads too
        self.assertTrue(self.env.ref("base.user_admin").has_group("clara_purchase_bridge.group_clara_admin"))

    def test_accounting_reads_the_clara_menu(self):
        accountant = self._user("account.group_account_invoice", "contador@test.local")
        self.assertTrue(accountant.has_group("clara_purchase_bridge.group_clara_reader"))
        self.assertFalse(accountant.has_group("clara_purchase_bridge.group_clara_admin"))
