from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestCostValidator(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env["ir.config_parameter"].sudo()
        # purchase_price_validation may be installed next to this module (a build installs every module of the repository)
        # and its own checks block and divert the confirmation when they are on: these tests are about this validator alone
        icp.set_param("purchase_price_validation.enable_purchase_validation", "False")
        icp.set_param("purchase_price_validation.enable_stock_validation", "False")
        icp.set_param("purchase_cost_validator.gross_factor", "2.0")
        icp.set_param("purchase_cost_validator.hold_receipt", "True")
        icp.set_param("purchase_cost_validator.start_date", "2000-01-01 00:00:00")
        cls.vendor = cls.env["res.partner"].create({"name": "Lácteos prueba"})
        cls.milk = cls.env["product.product"].create({"name": "LECHE ENTERA PRUEBA", "type": "consu", "is_storable": True, "standard_price": 3000, "porcent_variation": 10})
        cls.dozen = cls.env.ref("uom.product_uom_dozen")
        cls.reviewer = new_test_user(cls.env, login="don.andres.test", name="Andrés Revisor", groups="base.group_user,purchase.group_purchase_user,stock.group_stock_user")
        cls.store = new_test_user(cls.env, login="tienda.test", name="Tienda Prueba", groups="base.group_user,purchase.group_purchase_user,stock.group_stock_user")
        icp.set_param("purchase_cost_validator.reviewer_user_id", str(cls.reviewer.id))

    @classmethod
    def _po(cls, env, qty, price, uom=None):
        return env["purchase.order"].create({"partner_id": cls.vendor.id, "order_line": [(0, 0, {
            "product_id": cls.milk.id, "product_qty": qty, "price_unit": price, "product_uom_id": (uom or cls.milk.uom_id).id})]})

    def _state(self, qty, price, uom=None):
        line = self._po(self.env, qty, price, uom).order_line
        return line.cost_check_state, line

    def test_line_colours_follow_the_product_rules(self):
        self.assertEqual(self._state(20, 3100)[0], "ok")         # inside the 10 % of the product
        self.assertEqual(self._state(20, 3600)[0], "warning")    # +20 %: the rule the module always had, in yellow
        state, line = self._state(20, 50000)                     # 20 milks for 1 000 000
        self.assertEqual(state, "danger")
        self.assertAlmostEqual(line.cost_check_reference, 3000)
        self.assertIn("unidad de medida", line.cost_check_message)
        self.assertEqual(self._state(20, 0)[0], "danger")        # zero price: free stock
        self.assertEqual(line.cost_check_field, "price")          # x16.7 is not a packing multiple: the price is wrong
        box = self._state(20, 300000)[1]                          # x100: a box of 100 typed as one unit
        self.assertEqual((box.cost_check_state, box.cost_check_field), ("danger", "quantity"))
        odd = self._state(20, 9000)[1]                            # x3: just a wrong price
        self.assertEqual((odd.cost_check_state, odd.cost_check_field), ("danger", "price"))

    def test_units_of_measure_are_converted(self):
        self.assertEqual(self._state(2, 36000, self.dozen)[0], "ok")       # 36 000 a dozen = 3 000 a unit
        state, line = self._state(2, 3000, self.dozen)                      # the unit price typed on a dozen
        self.assertEqual(state, "danger")
        self.assertAlmostEqual(line.cost_check_reference, 36000)

    def test_cost_and_product_margin_are_the_rules(self):
        new = self.env["product.product"].create({"name": "AVENA PRUEBA", "type": "consu", "is_storable": True, "standard_price": 1000})
        po = self.env["purchase.order"].create({"partner_id": self.vendor.id, "order_line": [(0, 0, {"product_id": new.id, "product_qty": 5, "price_unit": 5000})]})
        self.assertEqual(po.order_line.cost_check_state, "danger")
        self.assertIn("costo del producto", po.order_line.cost_check_message)
        wide = self.env["product.product"].create({"name": "FRUTA PRUEBA", "type": "consu", "is_storable": True, "standard_price": 1000, "porcent_variation": 30})
        po = self.env["purchase.order"].create({"partner_id": self.vendor.id, "order_line": [(0, 0, {"product_id": wide.id, "product_qty": 5, "price_unit": 1250})]})
        self.assertEqual(po.order_line.cost_check_state, "ok")      # +25 % is inside this product's own 30 % margin
        free = self.env["product.product"].create({"name": "SIN COSTO PRUEBA", "type": "consu", "is_storable": True, "standard_price": 0})
        po = self.env["purchase.order"].create({"partner_id": self.vendor.id, "order_line": [(0, 0, {"product_id": free.id, "product_qty": 5, "price_unit": 1250})]})
        self.assertEqual(po.order_line.cost_check_state, "none")    # no cost recorded: nothing to compare with

    def test_confirming_never_blocks_and_leaves_a_trace(self):
        po = self._po(self.env(user=self.store), 20, 50000)
        po.sudo().message_subscribe(partner_ids=self.vendor.ids)     # the vendor follows its own orders
        self.assertEqual((po.cost_check_state, po.cost_check_count), ("danger", 1))
        po.button_confirm()
        self.assertEqual(po.state, "purchase")
        self.assertTrue(po.cost_alert)
        self.assertTrue(any("desfase de costo" in (m.body or "") for m in po.message_ids))
        # the reviewer is told at confirmation (message + to-do), not only at the receipt
        self.assertTrue(po.message_ids.filtered(lambda m: self.reviewer.partner_id in m.partner_ids))
        self.assertTrue(po.activity_ids.filtered(lambda a: a.user_id == self.reviewer))
        # the internal alert never reaches the vendor, even as a follower
        self.assertFalse(po.message_ids.filtered(lambda m: self.vendor in m.notified_partner_ids))

    def test_receipt_is_held_and_the_reviewer_notified(self):
        po = self._po(self.env, 20, 50000)
        po.button_confirm()
        picking = po.picking_ids
        picking.move_ids.quantity = 20
        action = picking.with_user(self.store).button_validate()
        self.assertEqual(action["res_model"], "purchase.cost.review.wizard")
        self.assertNotEqual(picking.state, "done")                          # the damaged cost did not get in
        self.assertTrue(picking.cost_alert)
        msg = picking.message_ids.filtered(lambda m: self.reviewer.partner_id in m.partner_ids)
        self.assertTrue(msg, "the reviewer gets the message (e-mail or inbox)")
        self.assertTrue(picking.activity_ids.filtered(lambda a: a.user_id == self.reviewer))
        wizard = self.env["purchase.cost.review.wizard"].browse(action["res_id"])
        self.assertFalse(wizard.can_approve)
        # same problem again: no second message
        picking.with_user(self.store).button_validate()
        self.assertEqual(len(picking.message_ids.filtered(lambda m: self.reviewer.partner_id in m.partner_ids)), 1)
        # the reviewer receives anyway: logged and closed
        action = picking.with_user(self.reviewer).button_validate()
        wizard = self.env["purchase.cost.review.wizard"].with_user(self.reviewer).browse(action["res_id"])
        self.assertTrue(wizard.can_approve)
        wizard.action_approve()
        self.assertEqual(picking.state, "done")
        self.assertEqual(picking.cost_approved_by, self.reviewer)
        self.assertFalse(picking.activity_ids.filtered(lambda a: a.user_id == self.reviewer))

    def test_corrected_order_receives_normally(self):
        po = self._po(self.env, 20, 50000)
        po.button_confirm()
        picking = po.picking_ids
        picking.move_ids.quantity = 20
        picking.with_user(self.store).button_validate()
        self.assertTrue(picking.cost_alert)
        po.order_line.price_unit = 3050      # the reviewer fixes the price on the order
        picking.with_user(self.store).button_validate()
        self.assertEqual(picking.state, "done")
        self.assertFalse(picking.cost_alert)

    def test_receiving_much_more_than_ordered_is_flagged(self):
        po = self._po(self.env, 10, 3000)
        po.button_confirm()
        picking = po.picking_ids
        picking.move_ids.quantity = 120      # a dozen box counted as units
        self.assertEqual(picking.cost_check_state, "danger")
        action = picking.with_user(self.store).button_validate()
        self.assertEqual(action["res_model"], "purchase.cost.review.wizard")

    def test_without_hold_the_receipt_goes_on_but_the_reviewer_knows(self):
        self.env["ir.config_parameter"].sudo().set_param("purchase_cost_validator.hold_receipt", False)
        po = self._po(self.env, 20, 50000)
        po.button_confirm()
        picking = po.picking_ids
        picking.move_ids.quantity = 20
        picking.with_user(self.store).button_validate()
        self.assertEqual(picking.state, "done")
        self.assertTrue(picking.cost_alert)
        self.assertTrue(picking.message_ids.filtered(lambda m: self.reviewer.partner_id in m.partner_ids))

    def test_own_settings_screen_saves_its_parameters(self):
        config = self.env["purchase.cost.validator.config"].create({})
        self.assertEqual((config.reviewer_id, config.hold_receipt), (self.reviewer, True))
        config.write({"reviewer_id": self.store.id, "hold_receipt": False, "gross_factor": 3})
        config.action_save()
        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.get_param("purchase_cost_validator.reviewer_user_id"), str(self.store.id))
        self.assertEqual(icp.get_param("purchase_cost_validator.hold_receipt"), "False")
        self.assertEqual(self.env["stock.picking"]._cost_check_reviewers(), self.store)

    def test_orders_before_the_go_live_stay_as_they_are(self):
        po = self._po(self.env, 20, 50000)    # an order that already existed when the validator went live
        po.button_confirm()
        tomorrow = fields.Datetime.to_string(fields.Datetime.add(fields.Datetime.now(), days=1))
        self.env["ir.config_parameter"].sudo().set_param("purchase_cost_validator.start_date", tomorrow)
        po.invalidate_recordset()
        po.order_line.invalidate_recordset()
        self.assertFalse(po.order_line.cost_check_state)            # not checked, not coloured
        self.assertEqual(po.cost_check_state, "ok")
        picking = po.picking_ids
        picking.move_ids.quantity = 20
        picking.with_user(self.store).button_validate()
        self.assertEqual(picking.state, "done")                     # received as always
        self.assertFalse(picking.cost_alert)
        self.assertFalse(picking.message_ids.filtered(lambda m: self.reviewer.partner_id in m.partner_ids))

    def test_new_order_being_typed_is_checked(self):
        tomorrow = fields.Datetime.to_string(fields.Datetime.add(fields.Datetime.now(), days=1))
        self.env["ir.config_parameter"].sudo().set_param("purchase_cost_validator.start_date", tomorrow)
        draft = self.env["purchase.order"].new({"partner_id": self.vendor.id, "order_line": [(0, 0, {"product_id": self.milk.id, "product_qty": 20, "price_unit": 50000})]})
        self.assertEqual(draft.order_line.cost_check_state, "danger")   # not saved yet = new

    def test_consumables_are_checked_services_are_not(self):
        coffee = self.env["product.product"].create({"name": "ACT 340 G PRUEBA", "type": "consu", "standard_price": 14580})
        po = self.env["purchase.order"].create({"partner_id": self.vendor.id, "order_line": [(0, 0, {"product_id": coffee.id, "product_qty": 10, "price_unit": 100000000})]})
        self.assertEqual(po.order_line.cost_check_state, "danger")
        service = self.env["product.product"].create({"name": "SERVICIO PRUEBA", "type": "service", "standard_price": 100})
        po = self.env["purchase.order"].create({"partner_id": self.vendor.id, "order_line": [(0, 0, {"product_id": service.id, "product_qty": 1, "price_unit": 100000})]})
        self.assertFalse(po.order_line.cost_check_state)

    def test_a_failure_of_the_check_never_blocks_the_flow(self):
        po = self._po(self.env, 20, 50000)
        with patch("odoo.addons.purchase_cost_validator.models.purchase_order.PurchaseOrder._cost_check_log_confirmation", side_effect=RuntimeError("boom")):
            po.button_confirm()
        self.assertEqual(po.state, "purchase")                       # confirmed although the note failed
        picking = po.picking_ids
        picking.move_ids.quantity = 20
        with patch("odoo.addons.purchase_cost_validator.models.stock_picking.StockPicking._cost_check_issues", side_effect=RuntimeError("boom")):
            picking.with_user(self.store).button_validate()
        self.assertEqual(picking.state, "done")                      # received although the check failed

    def test_holding_receipts_is_off_by_default(self):
        self.env["ir.config_parameter"].sudo().search([("key", "=", "purchase_cost_validator.hold_receipt")]).unlink()
        po = self._po(self.env, 20, 50000)
        po.button_confirm()
        picking = po.picking_ids
        picking.move_ids.quantity = 20
        picking.with_user(self.store).button_validate()
        self.assertEqual(picking.state, "done")                      # nothing is held unless someone turns it on
        self.assertTrue(picking.cost_alert)                          # but it is flagged and the reviewer is told

    def test_cost_edit_warns_but_never_blocks_or_changes_the_cost(self):
        product = self.env["product.product"].create({"name": "CAFE COSTO PRUEBA", "type": "consu", "is_storable": True, "standard_price": 1000})
        product.write({"standard_price": 1100})                                   # +10 %: nothing
        self.assertFalse(product.product_tmpl_id.message_ids.filtered(lambda m: self.reviewer.partner_id in m.partner_ids))
        product.with_user(self.store).sudo().write({"standard_price": 1000000})   # a kilo typed as a gram
        self.assertEqual(product.standard_price, 1000000)                          # saved exactly as typed
        notes = product.product_tmpl_id.message_ids.filtered(lambda m: self.reviewer.partner_id in m.partner_ids)
        self.assertEqual(len(notes), 1)
        self.assertIn("veces más alto", notes.body)
        self.assertTrue(product.product_tmpl_id.activity_ids.filtered(lambda a: a.user_id == self.reviewer))

    def test_cost_edit_ignores_first_cost_automatic_changes_and_failures(self):
        product = self.env["product.product"].create({"name": "COSTO NUEVO PRUEBA", "type": "consu", "is_storable": True, "standard_price": 0})
        product.write({"standard_price": 5000})                                    # first cost: never flagged
        product.with_context(disable_auto_svl=True).write({"standard_price": 900000})   # automatic recalculation (Odoo 17 mark): ignored
        product.with_context(disable_auto_revaluation=True).write({"standard_price": 800000})   # same, Odoo 19 mark: ignored
        self.assertFalse(product.product_tmpl_id.message_ids.filtered(lambda m: self.reviewer.partner_id in m.partner_ids))
        with patch("odoo.addons.purchase_cost_validator.models.product_product.ProductProduct._cost_edit_notify", side_effect=RuntimeError("boom")):
            product.write({"standard_price": 10})
        self.assertEqual(product.standard_price, 10)                               # saved although the check failed

    def test_without_reviewer_purchase_managers_by_inheritance_are_told(self):
        """Sin revisor se avisa a los administradores de compras, también a quien lo es por otro grupo (17: group.users)."""
        self.env["ir.config_parameter"].sudo().set_param("purchase_cost_validator.reviewer_user_id", "")
        boss_group = self.env["res.groups"].create({"name": "Jefe de compras prueba",
                                                    "implied_ids": [(4, self.env.ref("purchase.group_purchase_manager").id)]})
        boss = new_test_user(self.env, login="jefe.compras.test", name="Jefe compras", groups="base.group_user")
        boss.group_ids = [(4, boss_group.id)]
        reviewers = self.env["stock.picking"]._cost_check_reviewers()
        self.assertIn(boss, reviewers)
        self.assertNotIn(self.env.ref("base.user_root"), reviewers)

    def test_average_cost_recalculated_by_a_receipt_is_not_a_manual_edit(self):
        """Odoo 19 recalcula el costo promedio con disable_auto_revaluation: no es una edición y no debe avisar."""
        self.env["ir.config_parameter"].sudo().set_param("purchase_cost_validator.hold_receipt", "False")
        categ = self.env["product.category"].create({"name": "AVCO PRUEBA", "property_cost_method": "average"})
        product = self.env["product.product"].create({"name": "AVCO PRUEBA", "type": "consu", "is_storable": True,
                                                      "categ_id": categ.id, "standard_price": 1000})
        po = self.env["purchase.order"].create({"partner_id": self.vendor.id, "order_line": [(0, 0, {
            "product_id": product.id, "product_qty": 10, "price_unit": 10000, "product_uom_id": product.uom_id.id})]})
        po.button_confirm()
        picking = po.picking_ids
        picking.move_ids.quantity = 10
        picking.with_user(self.store).button_validate()
        self.assertEqual(picking.state, "done")
        self.assertTrue(picking.cost_alert)                                       # la recepción sí avisa (precio 10x)
        if product.standard_price == 1000:
            self.skipTest("el núcleo no recalculó el costo promedio en esta recepción")
        self.assertFalse(product.product_tmpl_id.message_ids.filtered(lambda m: "Cambio de costo incoherente" in (m.body or "")))

    def test_cost_edit_banner_text(self):
        Product = self.env["product.product"]
        self.assertFalse(Product._cost_edit_message(1000, 1500))
        self.assertIn("unidad correcta", Product._cost_edit_message(1000, 1000000))   # x1000: gram vs kilo
        self.assertIn("cero", Product._cost_edit_message(1000, 0))
        self.assertFalse(Product._cost_edit_message(0, 5000))

    def test_configuration_is_for_administrators_only(self):
        manager = new_test_user(self.env, login="gerente.compras.test", name="Gerente compras", groups="base.group_user,purchase.group_purchase_manager,stock.group_stock_manager")
        menu = self.env.ref("purchase_cost_validator.menu_purchase_cost_validator_config")
        config = self.env["purchase.cost.validator.config"]
        for user, allowed in ((self.env.ref("base.user_admin"), True), (manager, False), (self.store, False), (self.reviewer, False)):
            self.assertEqual(menu.id in self.env["ir.ui.menu"].with_user(user)._visible_menu_ids(), allowed, user.name)   # what the web client builds the menu from
            self.assertEqual(config.with_user(user).check_access_rights("read", raise_exception=False), allowed, user.name)
        # what everybody needs keeps working: the warning on the order and the review window of a held receipt
        self.assertTrue(self.env["purchase.cost.review.wizard"].with_user(self.store).check_access_rights("create", raise_exception=False))

    def test_it_does_not_depend_on_the_old_validation_module(self):
        """The old module blocks orders when its checks are on (and Odoo's settings page switches them on by deleting
        their parameters), and confirming through its dialog skips this validator."""
        import ast
        import os
        manifest_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "__manifest__.py")
        with open(manifest_path) as f:
            manifest = ast.literal_eval(f.read())
        self.assertNotIn("purchase_price_validation", manifest["depends"])
        self.assertEqual(self.env["product.template"]._fields["porcent_variation"].default(self.env["product.template"]), 10.0)

    def test_it_coexists_with_the_old_module_and_its_dialog(self):
        """With purchase_price_validation installed and its checks on, Confirmar opens its dialog and confirming there
        skips button_confirm: the validator must still flag the order and write its note, and nothing is switched off."""
        if "confirmation.variation.wizard" not in self.env:
            self.skipTest("purchase_price_validation is not installed")
        self.env["ir.config_parameter"].sudo().set_param("purchase_price_validation.enable_purchase_validation", "True")
        po = self._po(self.env, 20, 50000)
        action = po.button_confirm()
        self.assertEqual(action["res_model"], "confirmation.variation.wizard")      # the old module's own dialog still opens
        self.assertEqual(po.state, "draft")
        self.env["confirmation.variation.wizard"].create({"purchase_order_id": po.id, "message": "x"}).action_confirm()
        self.assertEqual(po.state, "purchase")
        self.assertTrue(po.cost_alert)                                              # flagged for the list
        self.assertTrue(any("desfase de costo" in (m.body or "") for m in po.message_ids))   # and noted in the history
        self.assertEqual(len([m for m in po.message_ids if "confirmada con desfase" in (m.body or "")]), 1)
