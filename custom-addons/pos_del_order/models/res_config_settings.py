# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # pos.config fields
    pos_del_able_employee_ids = fields.Many2many(
        'hr.employee',
        related='pos_config_id.able_del_employee_ids',
        readonly=False,
        string="Employees able to cancel orders",
        help="List of employees able to cancel orders"
    )
