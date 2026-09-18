# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from odoo.addons.portal.controllers.portal import CustomerPortal


class MaintenanceManagementPortal(CustomerPortal):
    """Expone la hoja de vida del equipo en el portal público.

    La misma ruta atiende tanto a usuarios anónimos que escanean el QR
    (validados por access_token) como a usuarios logueados con acceso al
    registro (validados por sus permisos habituales).
    """

    @http.route(
        ['/my/equipment/<int:equipment_id>'],
        type='http', auth='public', website=True,
    )
    def portal_equipment_hoja_vida(self, equipment_id, access_token=None, **kw):
        try:
            equipment_sudo = self._document_check_access(
                'maintenance.equipment', equipment_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        values = {
            'equipment': equipment_sudo,
            'page_name': 'equipment_hoja_vida',
        }
        return request.render(
            'maintenance_management.portal_equipment_hoja_vida', values)
