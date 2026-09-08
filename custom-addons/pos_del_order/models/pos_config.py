# -*- coding: utf-8 -*-

from odoo import models, fields


class PosConfig(models.Model):
    _inherit = 'pos.config'

    able_del_employee_ids = fields.Many2many(
        'hr.employee',
        relation='pos_config_able_del_employee_rel',
        column1='pos_config_id',
        column2='employee_id',
        string="Employees able to delete orders",
        help='If left empty, all employees can delete orders in the PoS session'
    )
