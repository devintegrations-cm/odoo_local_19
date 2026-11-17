# -*- coding: utf-8 -*-
"""Clara settings, for "Clara / Administrador" only: the API connection and the weekly sync parameters."""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.clara_api_service import ClaraAPIService

_logger = logging.getLogger(__name__)

ADMIN_GROUP = "clara_purchase_bridge.group_clara_admin"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    clara_country = fields.Selection(related="company_id.clara_country", readonly=False)
    clara_client_id = fields.Char(related="company_id.clara_client_id", readonly=False, groups=ADMIN_GROUP)
    clara_client_secret = fields.Char(related="company_id.clara_client_secret", readonly=False, groups=ADMIN_GROUP)
    clara_tax_identifier = fields.Char(related="company_id.clara_tax_identifier", readonly=False)
    clara_ca_cert = fields.Binary(related="company_id.clara_ca_cert", readonly=False, groups=ADMIN_GROUP)
    clara_client_cert = fields.Binary(related="company_id.clara_client_cert", readonly=False, groups=ADMIN_GROUP)
    clara_client_key = fields.Binary(related="company_id.clara_client_key", readonly=False, groups=ADMIN_GROUP)
    clara_cert_uploaded_date = fields.Datetime(related="company_id.clara_cert_uploaded_date", readonly=True)

    clara_request_timeout = fields.Integer("Tiempo máximo por llamada (segundos)", config_parameter="clara_connector.clara_request_timeout", default=30)
    clara_page_size = fields.Integer("Transacciones por página", config_parameter="clara_connector.page_size", default=100,
                                     help="Tamaño de página pedido a Clara (máximo 100, el de la API). Cada página es una llamada.")
    clara_sync_start_date = fields.Datetime("Primera sincronización desde", config_parameter="clara_connector.sync_start_date",
                                            help="Solo cuenta para la primera sincronización: fecha de operación desde la que se leen las transacciones. "
                                                 "Después, cada corrida pide únicamente lo creado o modificado en Clara desde la corrida anterior.")
    clara_sync_overlap_days = fields.Integer("Días que se releen", config_parameter="clara_connector.sync_overlap_days", default=1,
                                             help="Margen de seguridad: cada corrida pide lo modificado desde la fecha de la corrida anterior menos estos días.")
    clara_monthly_call_limit = fields.Integer("Límite mensual de llamadas a Clara", config_parameter="clara_connector.monthly_call_limit", default=2500,
                                              help="El plan de Libertario incluye unas 3.000 llamadas al mes.")
    clara_last_sync_date = fields.Char("Última sincronización", compute="_compute_clara_sync_info")
    clara_calls_this_month = fields.Integer("Llamadas este mes", compute="_compute_clara_sync_info")

    @api.depends("company_id")
    def _compute_clara_sync_info(self):
        icp = self.env["ir.config_parameter"].sudo()
        Transaction = self.env["clara.transaction"]
        for settings in self:
            settings.clara_last_sync_date = icp.get_param("clara_connector.last_sync_date") or _("Nunca")
            settings.clara_calls_this_month = Transaction._calls_this_month()

    @api.onchange("clara_ca_cert", "clara_client_cert", "clara_client_key")
    def _onchange_clara_certs(self):
        if any([self.clara_ca_cert, self.clara_client_cert, self.clara_client_key]):
            self.clara_cert_uploaded_date = fields.Datetime.now()

    def action_test_clara_connection(self):
        """Saves the page, asks for a token and reads one transaction (one GET)."""
        self.ensure_one()
        self.execute()
        service = ClaraAPIService(self.env)
        try:
            service.get_token()
            service.get_transactions(limit=1, max_records=1)
        except Exception as e:  # noqa: BLE001
            raise UserError(_("La conexión falló: %s") % e)
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": _("Conexión correcta"), "message": _("Odoo se conectó a la API de Clara y obtuvo el token."), "type": "success", "sticky": False}}

    def action_clara_sync_now(self):
        """Saves the page and runs the weekly sync by hand."""
        self.ensure_one()
        self.set_values()
        return self.env["clara.transaction"].action_sync_now()
