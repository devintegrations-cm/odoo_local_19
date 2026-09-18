# -*- coding: utf-8 -*-
from odoo import fields, models


class MaintenanceChecklistTemplate(models.Model):
    _name = 'maintenance.checklist.template'
    _description = 'Plantilla de checklist'

    name = fields.Char(
        string="Nombre",
        required=True,
    )
    category_id = fields.Many2one(
        'maintenance.equipment.category',
        string="Categoría de equipo",
    )
    line_ids = fields.One2many(
        'maintenance.checklist.template.line', 'template_id',
        string="Ítems",
    )


class MaintenanceChecklistTemplateLine(models.Model):
    _name = 'maintenance.checklist.template.line'
    _description = 'Ítem de plantilla de checklist'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'maintenance.checklist.template',
        string="Plantilla",
        ondelete='cascade',
        required=True,
    )
    name = fields.Char(
        string="Ítem",
        required=True,
    )
    sequence = fields.Integer(
        string="Secuencia",
        default=10,
    )


class MaintenanceChecklistLine(models.Model):
    _name = 'maintenance.checklist.line'
    _description = 'Ítem de checklist de mantenimiento'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'maintenance.request',
        string="Solicitud de mantenimiento",
        ondelete='cascade',
        required=True,
    )
    name = fields.Char(
        string="Ítem",
        required=True,
    )
    is_done = fields.Boolean(
        string="Realizado",
    )
    note = fields.Char(
        string="Nota",
    )
    sequence = fields.Integer(
        string="Secuencia",
        default=10,
    )
