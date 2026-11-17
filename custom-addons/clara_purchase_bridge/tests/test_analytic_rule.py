"""The cardholder table: which rule a cardholder gets (Clara uuid, email, exact name, then the area default) and
how the standard analytic names are linked to the accounts that exist in Odoo. Nothing is guessed: a name shared
by several rules, or a rule whose uuid is not the cardholder's, gives no rule."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAnalyticRule(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Rule = self.env["clara.analytic.rule"]
        plan = self.env["account.analytic.plan"].create({"name": "Test plan"})
        Account = self.env["account.analytic.account"]
        self.admin = Account.create({"name": "[TADM] Administrativo Test - Empresa Test", "plan_id": plan.id})
        self.institutional = Account.create({"name": "[TINS] Institucional Test - Empresa Test", "plan_id": plan.id})
        self.ana = self.Rule.create({"name": "Ana Test", "cardholder_email": "ana@test.local", "area": "FINANCIERA",
                                     "analytic_distribution": {str(self.admin.id): 100.0}})
        self.Rule.create({"name": "Osmar IT Test", "area": "IT", "multi_cost_center": True})

    def test_rule_by_uuid_email_or_exact_name(self):
        self.ana.cardholder_uuid = "UUID-ANA-0001"
        self.assertEqual(self.Rule._find_for(cardholder="nadie", uuid=" uuid-ana-0001 "), self.ana)
        self.assertEqual(self.Rule._find_for(cardholder="A. Test", email="ANA@test.local"), self.ana)
        self.assertEqual(self.Rule._find_for(cardholder="  ANA   TEST "), self.ana)
        self.assertFalse(self.Rule._find_for(cardholder="Persona Sin Regla"))
        self.assertEqual(self.ana._first_account(), self.admin)
        self.assertEqual(self.ana._account_names(), self.admin.name)

    def test_doubts_give_no_rule(self):
        """The name matches but the uuid is another person's, or two rules share the name without a stronger key."""
        self.ana.cardholder_uuid = "UUID-ANA-0001"
        rule, problem = self.Rule._lookup(cardholder="Ana Test", uuid="uuid-someone-else")
        self.assertFalse(rule)
        self.assertIn("uuid de Clara es otro", problem)
        self.Rule.create({"name": "Doble Test", "area": "FINANCIERA", "analytic_distribution": {str(self.admin.id): 100.0}})
        self.Rule.create({"name": "Doble Test", "area": "LEGAL", "analytic_distribution": {str(self.admin.id): 100.0}})
        rule, problem = self.Rule._lookup(cardholder="doble test")
        self.assertFalse(rule)
        self.assertIn("2 reglas de titular", problem)

    def test_area_default_for_cardholders_without_a_deciding_rule(self):
        area_rule = self.Rule.create({"name": "LEGAL", "kind": "area", "area": "LEGAL", "analytic_distribution": {str(self.admin.id): 100.0}})
        self.assertEqual(self.Rule._find_for(cardholder="Persona Sin Regla", area="legal"), area_rule)
        without_account = self.Rule.create({"name": "Regla Sin Cuenta Test", "area": "LEGAL"})
        self.assertEqual(self.Rule._find_for(cardholder="Regla Sin Cuenta Test"), area_rule)   # the rule's own area decides
        self.assertFalse(without_account._first_account())
        # a multi-cost-centre rule decides by itself: no area default and no fixed account
        osmar = self.Rule._find_for(cardholder="Osmar IT Test", area="LEGAL")
        self.assertEqual((osmar.name, osmar.multi_cost_center, osmar._first_account()), ("Osmar IT Test", True, self.env["account.analytic.account"]))

    def test_standard_names_are_linked_to_existing_accounts(self):
        rule = self.Rule.create({"name": "Nuevo Titular Test", "area": "COMERCIAL", "analytic_name": "Institucional Test"})
        self.assertFalse(rule._distribution())
        self.assertEqual(rule.action_resolve_analytic_accounts(), 1)
        self.assertEqual(rule._first_account(), self.institutional)
        unknown = self.Rule.create({"name": "Otro Titular Test", "area": "COMERCIAL", "analytic_name": "Centro Inexistente Test"})
        self.assertEqual(unknown.action_resolve_analytic_accounts(), 0)
        self.assertFalse(unknown._distribution())

    def test_table_never_stores_a_national_id(self):
        self.assertNotIn("cardholder_vat", self.Rule._fields)
        self.assertNotIn("vat_key", self.Rule._fields)
