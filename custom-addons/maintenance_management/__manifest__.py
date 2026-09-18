# -*- coding: utf-8 -*-
{
    'name': 'Gestión Integral de Mantenimiento',
    'version': '19.0.1.0.0',
    'summary': 'Gestión integral de equipos y solicitudes de mantenimiento con QR, '
               'checklist de mantenimiento y control de costos.',
    'description': """
Gestión Integral de Mantenimiento
==================================
Extiende el módulo de Mantenimiento de Odoo con:
  - Número de activo, almacén/tienda y cliente asociado al equipo.
  - Código QR y hoja de vida del equipo publicada en el portal.
  - Costo total de mantenimientos por equipo.
  - Líneas de costo por solicitud de mantenimiento, con opción de traerlas
    desde una orden de compra.
  - Checklist de mantenimiento configurable por categoría de equipo, con
    validación opcional antes de cerrar una solicitud.
""",
    'author': 'Maintenance Management',
    'category': 'Manufacturing/Maintenance',
    'depends': ['maintenance', 'portal', 'purchase', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/system_parameters.xml',
        'data/server_actions.xml',
        'report/qr_label_report.xml',
        'report/maintenance_report.xml',
        'views/maintenance_checklist_views.xml',
        'views/maintenance_equipment_views.xml',
        'views/maintenance_request_views.xml',
        'views/maintenance_portal_templates.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
