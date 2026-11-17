# -*- coding: utf-8 -*-
from odoo import api, fields, models

ADMIN_GROUP = "clara_purchase_bridge.group_clara_admin"


class ResCompany(models.Model):
    _inherit = "res.company"

    clara_country = fields.Selection([("mx", "México"), ("co", "Colombia"), ("br", "Brasil")], string="País de Clara", default="co")
    # the credentials and certificates are read by "Clara / Administrador" only; the API service reads them as superuser
    clara_client_id = fields.Char("Client ID de Clara", groups=ADMIN_GROUP)
    clara_client_secret = fields.Char("Client Secret de Clara", groups=ADMIN_GROUP)
    clara_tax_identifier = fields.Char("NIT de la compañía en Clara")
    clara_ca_cert = fields.Binary(string="Certificado CA (.pem)", attachment=True, groups=ADMIN_GROUP)
    clara_client_cert = fields.Binary(string="Certificado del cliente (.crt)", attachment=True, groups=ADMIN_GROUP)
    clara_client_key = fields.Binary(string="Llave privada del cliente (.key)", attachment=True, groups=ADMIN_GROUP)
    clara_cert_uploaded_date = fields.Datetime("Certificados cargados el", readonly=True)

    CLARA_CREDENTIAL_FIELDS = ("clara_country", "clara_client_id", "clara_client_secret", "clara_ca_cert", "clara_client_cert", "clara_client_key")

    @api.onchange("clara_ca_cert", "clara_client_cert", "clara_client_key")
    def _onchange_clara_certs(self):
        if any([self.clara_ca_cert, self.clara_client_cert, self.clara_client_key]):
            self.clara_cert_uploaded_date = fields.Datetime.now()

    def write(self, vals):
        result = super().write(vals)
        if any(f in vals for f in self.CLARA_CREDENTIAL_FIELDS):
            # a token issued to the old credentials is useless (and misleading) with the new ones: ask for a new one
            self.env["ir.config_parameter"].sudo().search([("key", "in", ("clara_connector.access_token", "clara_connector.access_token_expiry"))]).unlink()
        return result
