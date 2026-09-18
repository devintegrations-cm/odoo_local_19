# Copyright 2024 ForgeFlow S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def get_views(self, views, options=None):
        """Rename the "Inventory at Date" button when locations are relevant.

        In Odoo 17 this button lived in the ``stock.quant`` views as
        ``<button name="action_inventory_at_date" type="object"/>``, so this module
        patched ``stock.quant.get_views``.

        In Odoo 19 the button moved to the ``product.product`` stock report view
        (``stock.product_product_stock_tree``) and became
        ``<button name="%(action_inventory_at_date)d" type="action"/>``, whose ``name``
        is resolved to the numeric id of the action. Hence both the model and the
        lookup had to change.
        """
        res = super().get_views(views, options=options)
        if not self.env.user.has_group("stock.group_stock_multi_locations"):
            return res
        list_view = res.get("views", {}).get("list", {})
        arch = list_view.get("arch", "")
        if not arch:
            return res
        action = self.env.ref("stock.action_inventory_at_date", raise_if_not_found=False)
        if not action:
            return res
        arch_tree = etree.XML(arch)
        buttons = arch_tree.xpath(f'//button[@name="{action.id}"]')
        if not buttons:
            return res
        for button in buttons:
            button.set("string", "Inventory at Date & Location")
        list_view["arch"] = etree.tostring(arch_tree, encoding="unicode")
        return res
