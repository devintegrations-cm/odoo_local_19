# -*- coding: utf-8 -*-

from functools import partial

from odoo import models, fields


class PosConfig(models.Model):
    _inherit = 'pos.config'

    able_del_pol_employee_ids = fields.Many2many(
        'hr.employee', string="Empleados que pueden borrar lineas de una orden",
        relation="abl_pol_employee_ids",
        help='Si un empleado no está en esta lista, no podrá borrar lineas de una orden que ya fueron enviadas a cocina.'
    )
