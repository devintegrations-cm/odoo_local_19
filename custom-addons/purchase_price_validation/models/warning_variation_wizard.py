# -*- coding: utf-8 -*-

from odoo import models, fields, api

class WarningVariationWizard(models.TransientModel):
    _name = 'warning.variation.wizard'
    _description = 'Wizard de advertencia'

    message = fields.Html(string="Mensaje", readonly=True, sanitize=False)

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
