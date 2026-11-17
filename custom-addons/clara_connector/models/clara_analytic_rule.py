# -*- coding: utf-8 -*-
"""When the cardholder table changes, the cards and transactions find their rule again (area and cost centre of the
dashboard). The rule itself lives in clara_purchase_bridge."""
from odoo import api, models

LINK_FIELDS = {"name", "kind", "cardholder_uuid", "cardholder_email", "area", "analytic_distribution", "multi_cost_center", "active", "company_id"}


class ClaraAnalyticRule(models.Model):
    _inherit = "clara.analytic.rule"

    def _relink_clara_records(self):
        for model in ("clara.transaction", "clara.card"):
            # "modified" on a dependency recomputes the rule link and what follows from it (area, analytic account)
            self.env[model].sudo().with_context(active_test=False).search([]).modified(["cardholder_uuid"])

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        rules._relink_clara_records()
        return rules

    def write(self, vals):
        result = super().write(vals)
        if LINK_FIELDS & set(vals):
            self._relink_clara_records()
        return result

    def unlink(self):
        result = super().unlink()
        self._relink_clara_records()
        return result
