# Copyright 2019 ForgeFlow S.L.
# Copyright 2021 Tecnativa - Víctor Martínez
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo import Command, fields

from .common import TestCommon


class TestStockQuantityHistoryLocation(TestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.main_company = cls.env.ref("base.main_company")
        cls.product = cls.env.ref("product.product_product_3")
        cls.test_stock_loc = cls.env["stock.location"].create(
            {
                "usage": "internal",
                "name": "Test Stock Location",
                "company_id": cls.main_company.id,
            }
        )
        cls.child_test_stock_loc = cls.env["stock.location"].create(
            {
                "usage": "internal",
                "name": "Child Test Stock Location",
                "location_id": cls.test_stock_loc.id,
                "company_id": cls.main_company.id,
            }
        )
        cls._create_stock_move(cls, location_dest_id=cls.child_test_stock_loc, qty=100)
        cls.group_multi_locations = cls.env.ref("stock.group_stock_multi_locations")

    def test_01_wizard_past_date(self):
        wizard = self.env["stock.quantity.history"].create(
            {
                "location_id": self.test_stock_loc.id,
                "include_child_locations": True,
                "inventory_datetime": fields.Datetime.now(),
            }
        )
        action = wizard.with_context(company_owned=True).open_at_date()
        self.assertEqual(
            self.product.with_context(**action["context"]).qty_available, 100.0
        )
        self.assertEqual(
            self.product.with_context(
                location=self.child_test_stock_loc.id, to_date="2019-08-10"
            ).qty_available,
            0.0,
        )

    def test_02_wizard_current(self):
        wizard = self.env["stock.quantity.history"].create(
            {"location_id": self.test_stock_loc.id, "include_child_locations": False}
        )
        action = wizard.with_context().open_at_date()
        self.assertEqual(action["context"]["compute_child"], False)
        self.assertEqual(action["context"]["location"], self.test_stock_loc.id)
        wizard = self.env["stock.quantity.history"].create(
            {"location_id": self.test_stock_loc.id, "include_child_locations": True}
        )
        action = wizard.with_context().open_at_date()
        self.assertEqual(action["context"]["compute_child"], True)
        self.assertEqual(action["context"]["location"], self.test_stock_loc.id)

    def _button_string(self, user):
        """Etiqueta del boton "Inventory at Date" tal como la ve `user`.

        El boton vive en la vista `stock.product_product_stock_tree`, que usa la accion
        "Stock" (`stock.action_product_stock_view`). No es la vista de lista por defecto
        de product.product, asi que hay que pedirla explicitamente.
        """
        view_id = self.env.ref("stock.product_product_stock_tree").id
        views = (
            self.env["product.product"].with_user(user).get_views([[view_id, "list"]])
        )
        arch = views.get("views", {}).get("list", {}).get("arch", "")
        buttons = etree.XML(arch).xpath("//header/button[@type='action']")
        # Si el boton dejara de existir, el test tiene que fallar, no pasar en silencio.
        self.assertEqual(
            len(buttons), 1, "Se esperaba exactamente un boton de accion en la cabecera"
        )
        return buttons[0].get("string")

    def test_03_button_label_depends_on_multi_location(self):
        """La etiqueta solo cambia para usuarios con ubicaciones multiples.

        En Odoo 19 el boton vive en la vista de product.product y el modulo le cambia
        la etiqueta con una vista heredada limitada por `group_ids`.
        """
        user = self.env["res.users"].create(
            {
                "name": "Tester almacen",
                "login": "tester_sqhl",
                "group_ids": [Command.link(self.env.ref("stock.group_stock_user").id)],
            }
        )
        self.assertEqual(self._button_string(user), "Inventory at Date")

        user.write({"group_ids": [Command.link(self.group_multi_locations.id)]})
        self.env["ir.ui.view"].clear_caches() if hasattr(
            self.env["ir.ui.view"], "clear_caches"
        ) else self.env.registry.clear_cache()
        self.assertEqual(self._button_string(user), "Inventory at Date & Location")
