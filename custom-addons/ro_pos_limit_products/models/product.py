# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.fields import Domain


class ProductTemplate(models.Model):
    _inherit = "product.template"

    ro_pos_config_ids = fields.Many2many(
        string='POS',
        comodel_name='pos.config'
    )

    @api.model
    def _load_pos_data_domain(self, data, config):
        """Only load in the POS the products linked to that point of sale.

        Odoo 19 replaced ``pos.config._get_available_product_domain()`` (Odoo 17)
        by this hook: ``point_of_sale/models/product_template.py:73``. It is the
        single place where the product domain of a session is built, and it is
        also reused by ``pos.config.get_product_loading_info()``
        (``point_of_sale/models/pos_config.py:910``).

        ``product.product`` needs no override: its own ``_load_pos_data_domain``
        only keeps the variants of the templates already loaded
        (``point_of_sale/models/product_product.py:11``).
        """
        domain = super()._load_pos_data_domain(data, config)
        return Domain.AND([domain, [('ro_pos_config_ids', 'in', config.ids)]])

    @api.model
    def _load_pos_data_fields(self, config):
        """Expone ro_pos_config_ids al POS para poder filtrar la grilla en el cliente."""
        result = super()._load_pos_data_fields(config)
        if "ro_pos_config_ids" not in result:
            result.append("ro_pos_config_ids")
        return result
