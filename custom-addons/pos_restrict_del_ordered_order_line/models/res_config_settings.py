# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # pos.config fields
    pos_able_del_pol_employee_ids = fields.Many2many(
        'hr.employee',
        related='pos_config_id.able_del_pol_employee_ids',
        readonly=False,
        string="Empleados que pueden borrar lineas de una orden",
        help="Lista de empleados que pueden borrar lineas de una orden en el punto de venta. Si un empleado no está en esta lista, no podrá borrar lineas de una orden que ya fueron enviadas a cocina."
    )
