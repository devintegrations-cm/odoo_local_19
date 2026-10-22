# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Detach dispersal methods from journals of another bank and fill outstanding accounts."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    journals = env['account.journal'].search([('type', '=', 'bank')])
    journals._cleanup_incompatible_dispersion_method_lines()
    journals._assign_dispersion_outstanding_accounts()
