# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Attach dispersal methods to journals identified by bank code, BIC or name."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    journals = env['account.journal'].search([('type', '=', 'bank')])
    journals._ensure_dispersion_method_lines()
    journals._cleanup_incompatible_dispersion_method_lines()
    journals._assign_dispersion_outstanding_accounts()
