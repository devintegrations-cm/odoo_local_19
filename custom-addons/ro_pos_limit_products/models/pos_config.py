# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = "pos.config"

    def open_ui(self):
        # In Odoo 19 ``close_ui()`` delegates to ``open_ui()``
        # (point_of_sale/models/pos_config.py:820), so the check only runs when a
        # new session is about to be opened; otherwise an already open session
        # could never be closed again.
        self.ensure_one()
        if not self.current_session_id:
            self._ro_check_pos_has_products()
        return super().open_ui()

    def _ro_check_pos_has_products(self):
        """Refuse to open a POS that would end up without a single product."""
        self.ensure_one()
        product_template = self.env['product.template']
        domain = product_template._load_pos_data_domain({}, self)
        if not product_template.search_count(domain, limit=1):
            raise ValidationError(_("There is no product linked to your PoS."))
